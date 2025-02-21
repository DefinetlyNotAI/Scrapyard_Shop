import os
import re
import time
import uuid
from datetime import datetime
from functools import wraps
from io import BytesIO
from typing import List

import psycopg2
import requests
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, request, redirect, url_for, flash
from flask import render_template_string, session, jsonify, make_response, abort
from flask import send_file
from flask import send_from_directory
from psycopg2._psycopg import DatabaseError
from psycopg2.extras import RealDictCursor
from waitress import serve
from werkzeug.security import check_password_hash, generate_password_hash

# ------------------------ FLASK APP, ------------------------- #
# ------------------ ENVIRONMENT VARIABLES -------------------- #
# ----------------------- AND TIME INIT ----------------------- #

# Flask app instance
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

START_TIME = time.time()

DB_URL_AIVEN = os.getenv("DB_URL_AIVEN")
DB_NAME = os.getenv("DB_NAME")
DOMAIN_NAME = "scrapyard-shop.vercel.app"  # Change me


# ------------------------- DATABASE ------------------------- #

# Database connection
def get_db_connection() -> psycopg2._psycopg.connection:
    conn = psycopg2.connect(DB_URL_AIVEN, dbname=DB_NAME)
    return conn


# Decorator to check if the user is an admin
def admin_required(param: callable):
    def wrap(*args, **kwargs):
        if 'team_name' not in session:
            if str(request.accept_mimetypes) != "*/*":
                return redirect(url_for('signin'))
            abort(403, description="Insufficient Permissions, User not logged in")
        if session['team_name'] != 'ADMIN':
            abort(403,
                  description=f"Insufficient Permissions, User {session['team_name']} is not admin")
        return param(*args, **kwargs)

    wrap.__name__ = param.__name__
    return wrap


# Decorator to rate limit the user - Advised not to use with @admin_required
def rate_limit(limit: int, time_window: int = 3600):
    # Create an independent store for each decorator instance
    request_store = {}

    def decorator(func):
        @wraps(func)  # Preserve the original function metadata
        def wrapper(*args, **kwargs):
            user_ip = request.remote_addr
            current_time = time.time()

            # Ensure user IP is in the request store
            if user_ip not in request_store:
                request_store[user_ip] = []

            timestamps = request_store[user_ip]
            valid_timestamps = [ts for ts in timestamps if current_time - ts <= time_window]
            request_store[user_ip] = valid_timestamps

            if len(valid_timestamps) >= limit:
                abort(429, description="Rate limit exceeded. Try again later.")

            request_store[user_ip].append(current_time)
            return func(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------- APIs ---------------------------- #
# ------------------------ Standalone --------------------------#

@app.route('/api/executeQuery', methods=['POST'])
@admin_required
def execute_query():
    query = request.json.get('query')
    if not query:
        return jsonify({"error": "No query provided"}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        if query.strip().lower().startswith("select"):
            results = cursor.fetchall()
        else:
            conn.commit()
            results = {"message": "Query executed successfully"}
        cursor.close()
        conn.close()
        return jsonify(results), 200
    except Exception:
        return jsonify({"error": "Query Execution Failed - API execute_query"}), 500


@app.route('/api/status', methods=['GET'])
def api_status():
    uptime = round(time.time() - START_TIME, 2)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        db_status = True
    except Exception:
        db_status = False

    return jsonify({
        "status": "API is running",
        "uptime_seconds": uptime,
        "database_connected": db_status
    })


# -------------------------- SHOP ------------------------------#

@app.route('/api/shop/buy', methods=['POST'])
@rate_limit(limit=30)
def buy():
    item_id = request.form.get('item_id')
    user_email = request.form.get('email')

    if not item_id or not user_email:
        flash("Invalid input! Make sure all fields are filled.", "error")
        return redirect(url_for('shop'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM item WHERE id = %s;', (item_id,))
    item = cur.fetchone()

    if item and item["stock"] > 0:
        cur.execute('INSERT INTO receipt (user_email, item_id) VALUES (%s, %s);', (user_email, item_id))
        conn.commit()

        # Fetch the image URL (stored in the `image` column of the database)
        item_image_url = item['image']  # Assuming this is the URL of the image

        # Generate receipt image and return as a downloadable file
        receipt_image_io = generate_receipt_image(user_email, item['name'], item['price'], item_image_url)

        # Return the image directly as a downloadable file without saving it
        return send_file(receipt_image_io, mimetype='image/png', as_attachment=True,
                         download_name=f"receipt_{str(uuid.uuid4())[:8]}.png")

    else:
        flash('Item out of stock!', 'error')

    cur.close()
    conn.close()
    return redirect(url_for('shop'))


@app.route('/api/shop/update_stock', methods=['POST'])
@admin_required
def update_stock():
    conn = get_db_connection()
    cur = conn.cursor()

    # Iterate through all posted stock values
    for key, value in request.form.items():
        if key.startswith("stock_"):  # The key will be in the form of 'stock_<item_id>'
            item_id = key.split("_")[1]
            new_stock = int(value)
            cur.execute('UPDATE item SET stock = %s WHERE id = %s;', (new_stock, item_id))

    conn.commit()
    cur.close()
    conn.close()
    flash("Stock updated successfully!", "success")
    return redirect(url_for('modify_stock'))


@app.route('/api/shop/cancel_receipt', methods=['POST'])
@admin_required
def cancel_receipt():
    receipt_id = request.form.get('receipt_id')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM receipt WHERE id = %s;', (receipt_id,))
    conn.commit()
    flash("Receipt cancelled!", "success")

    cur.close()
    conn.close()
    return redirect(url_for('volunteer'))


@app.route('/api/shop/remove_mission/<int:mission_id>', methods=['GET'])
@admin_required
def remove_mission(mission_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM missions WHERE id = %s;', (mission_id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Mission removed successfully!", "success")
    return redirect(url_for('missions'))


@app.route('/api/shop/add_mission', methods=['GET', 'POST'])
@admin_required
def add_mission():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        scraps = request.form.get('scraps')

        if not name or not description or not scraps:
            flash("All fields are required!", "error")
            return redirect(url_for('add_mission'))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO missions (name, description, scraps) VALUES (%s, %s, %s);',
                    (name, description, int(scraps)))
        conn.commit()
        cur.close()
        conn.close()

        flash("Mission added successfully!", "success")
        return redirect(url_for('missions'))

    return render_template_string(ADD_MISSION_TEMPLATE), 200


# ------------------------ END APIs ------------------------- #

# ------------------------ RESOURCES ------------------------ #


@app.route('/favicon.ico', methods=['GET'])
def get_favicon():
    try:
        return send_from_directory('static', 'favicon.png', mimetype='image/vnd.microsoft.icon'), 200
    except FileNotFoundError:
        return abort(404, description="Favicon not found")
    except Exception:
        return abort(500, description="Favicon fetching failed")


@app.route('/retry/<path:url_to_check>', methods=['POST'])
@rate_limit(limit=60)
def retry(url_to_check: str):
    try:
        # Validate and sanitize URL (remove protocol and www.)
        sanitized_url = re.sub(r'^(https?://)?(www\.)?', '', url_to_check)

        # Prevent SSRF by checking if the URL is in the whitelist
        if not any(re.fullmatch(pattern, sanitized_url) for pattern in allowed_urls()):
            return jsonify({
                "error_code": "URL_NOT_ALLOWED",
                "error_message": "URL not in whitelist. Contact the developer if this is unexpected.",
                "status_code": 406
            }), 406

        # Prevent retry loops
        if "retry" in url_to_check:
            return jsonify({
                "error_code": "INVALID_RETRY_CALL",
                "error_message": "You can't have a retry call within another retry call!",
                "status_code": 400
            }), 400

        # Attempt the request
        response = requests.get(url_to_check)

        # Return a structured JSON response
        return jsonify({
            "message": "Retry successful" if response.status_code == 200 else "Retry failed",
            "retried_url": url_to_check,
            "status_code": response.status_code,
            "response_text": response.text[:250]  # Limit response to prevent excessive logging
        }), response.status_code

    except requests.exceptions.ConnectionError:
        return jsonify({
            "error_code": "CONNECTION_ERROR",
            "error_message": "Failed to establish a connection to the server.",
            "status_code": 503
        }), 503

    except requests.exceptions.Timeout:
        return jsonify({
            "error_code": "TIMEOUT_ERROR",
            "error_message": "The request timed out.",
            "status_code": 504
        }), 504

    except requests.RequestException as e:
        return jsonify({
            "error_code": "REQUEST_FAILED",
            "error_message": f"Request error: {str(e)}",
            "status_code": 500
        }), 500

    except Exception as e:
        return jsonify({
            "error_code": "SERVER_ERROR",
            "error_message": f"Unexpected server error: {str(e)}",
            "status_code": 500
        }), 500


def allowed_urls() -> List[str]:
    allowed = []
    for rule in app.url_map.iter_rules():
        url = DOMAIN_NAME + str(rule)
        # Convert Flask URL rules to regex patterns
        url_pattern = re.sub(r'<[^>]+>', r'[^/]+', url)
        allowed.append(url_pattern)
    return allowed


# Modify the receipt generation to return the receipt image in-memory
def generate_receipt_image(user_email, item_name, item_price, item_image_url):
    receipt_id = str(uuid.uuid4())[:8]  # Shortened UUID
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create an image for the receipt
    img = Image.new("RGB", (400, 400), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 20)  # Change if missing
    except IOError:
        font = ImageFont.load_default()

    # Receipt text
    text = f"Receipt ID: {receipt_id}\nUser: {user_email}\nItem: {item_name}\nPrice: {item_price} scraps\nDate: {timestamp}"
    draw.text((20, 20), text, fill="black", font=font)

    # Fetch the image from the URL
    try:
        response = requests.get(item_image_url)
        if response.status_code == 200:
            item_image = Image.open(BytesIO(response.content))  # Load image from the URL content
            item_image = item_image.resize((100, 100))  # Resize if necessary
            img.paste(item_image, (20, 150))  # Paste the image onto the receipt
        else:
            raise Exception(f"Failed to fetch image: {response.status_code}")
    except Exception as e:
        print(f"Error loading item image: {e}")

    # Generate the image in memory
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return img_io


# ---------------------- ERROR HANDLERS --------------------- #

@app.errorhandler(400)
def bad_request(e):
    if str(request.accept_mimetypes) != "*/*":
        return render_template_string(ERROR_400_TEMPLATE, error_message=e.description), 403
    else:
        return jsonify({"error": e.description}), 403


@app.errorhandler(403)
def forbidden(e):
    if str(request.accept_mimetypes) != "*/*":
        return render_template_string(ERROR_403_TEMPLATE, error_message=e.description), 403
    else:
        return jsonify({"error": e.description}), 403


@app.errorhandler(404)
def page_not_found(e):
    if str(request.accept_mimetypes) != "*/*":
        return render_template_string(ERROR_404_TEMPLATE, error_message=e.description), 404
    else:
        return jsonify({"error": e.description}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    if str(request.accept_mimetypes) != "*/*":
        return render_template_string(ERROR_405_TEMPLATE, error_message=e.description), 405
    else:
        return jsonify({"error": e.description}), 405


@app.errorhandler(429)
def too_many_requests(e):
    if str(request.accept_mimetypes) != "*/*":
        return render_template_string(ERROR_429_TEMPLATE, error_message=e.description), 429
    else:
        return jsonify({"error": e.description}), 429


@app.errorhandler(500)
def internal_server_error(e):
    if str(request.accept_mimetypes) != "*/*":
        return render_template_string(ERROR_500_TEMPLATE, error_message=e.description), 500
    else:
        return jsonify({"error": e.description}), 500


# -------------------------- PAGES -------------------------- #

@app.route('/')
def home():
    if 'team_name' not in session or request.cookies.get('team_name') != session['team_name']:
        return redirect(url_for('signin'))
    if 'start_time' not in session:
        session['start_time'] = time.time()
    return redirect(url_for('shop'))


@app.route('/admin/shop')
@admin_required
def volunteer():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Perform a join to fetch item details alongside receipts
    cur.execute('''
        SELECT receipt.id, receipt.user_email, receipt.status, item.name, item.price
        FROM receipt
        JOIN item ON receipt.item_id = item.id
    ''')
    receipts = cur.fetchall()
    cur.close()
    conn.close()
    return render_template_string(ADMIN_RECEIPTS_TEMPLATE, receipts=receipts), 200


@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        team_name = request.form.get('team_name')
        password = request.form.get('password')
        if not team_name or not password:
            return render_template_string(SIGNIN_TEMPLATE, error="Team name and password are required."), 400

        conn = get_db_connection()

        cursor = conn.cursor()
        cursor.execute('SELECT password, ip_address FROM teams WHERE team_name = %s', (team_name,))
        result = cursor.fetchone()

        if result:
            stored_password, stored_ip = result
            if check_password_hash(stored_password, password):
                if stored_ip and stored_ip != request.remote_addr and team_name != 'ADMIN':
                    return render_template_string(SIGNIN_TEMPLATE,
                                                  error="Account is already in use from another device, only 1 account per device (Uses IP tracking) - To fix, please contact ADMIN"), 409
                session['team_name'] = team_name
                cursor.execute('UPDATE teams SET ip_address = %s WHERE team_name = %s',
                               (request.remote_addr, team_name))
            else:
                return render_template_string(SIGNIN_TEMPLATE, error="Invalid password."), 401
        else:
            hashed_password = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO teams (team_name, password, ip_address) VALUES (%s, %s, %s, %s)',
                (team_name, hashed_password, request.remote_addr, ''))
            session['team_name'] = team_name

        conn.commit()
        cursor.close()
        conn.close()

        resp = make_response(redirect(url_for('home')))
        resp.set_cookie('team_name', team_name, secure=True, samesite='Strict')
        return resp
    return render_template_string(SIGNIN_TEMPLATE), 200


@app.route('/shop')
def shop():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM item;')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template_string(STORE_TEMPLATE, items=items), 200


@app.route('/shop/modify_stock', methods=['GET'])
@admin_required
def modify_stock():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM item;')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template_string(MODIFY_STOCKS_TEMPLATE, items=items), 200


@app.route('/shop/add_item', methods=['GET', 'POST'])
@admin_required
def add_item():
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        image = request.form.get('image')
        description = request.form.get('description')
        stock = request.form.get('stock')

        if not name or not price or not image or not stock:
            flash("All fields except description are required!", "error")
            return redirect(url_for('add_item'))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO item (name, price, image, description, stock) VALUES (%s, %s, %s, %s, %s);',
                    (name, float(price), image, description, int(stock)))
        conn.commit()
        cur.close()
        conn.close()

        flash("Item added successfully!", "error")
        return redirect(url_for('shop'))

    return render_template_string(ADD_ITEM_TEMPLATE), 200


@app.route('/shop/missions')
def missions():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM missions;')
    mission = cur.fetchall()
    cur.close()
    conn.close()
    return render_template_string(MISSIONS_TEMPLATE, missions=mission), 200


# --------------------------- HTML --------------------------- #

# YES IK THIS IS NOT GOOD PRACTISE, BUT I KEPT GETTING WARNINGS
# IN PYCHARM THAT TEMPLATE IS UNDEFINED - SO I USED THIS
try:
    # HTML templates for sign-in, submit and leaderboard pages
    with open("template/signin.html", "r") as f:
        SIGNIN_TEMPLATE = f.read()

    # Error templates
    with open("template/error/400.html", "r") as f:
        ERROR_400_TEMPLATE = f.read()

    with open("template/error/403.html", "r") as f:
        ERROR_403_TEMPLATE = f.read()

    with open("template/error/404.html", "r") as f:
        ERROR_404_TEMPLATE = f.read()

    with open("template/error/405.html", "r") as f:
        ERROR_405_TEMPLATE = f.read()

    with open("template/error/429.html", "r") as f:
        ERROR_429_TEMPLATE = f.read()

    with open("template/error/500.html", "r") as f:
        ERROR_500_TEMPLATE = f.read()

    # Shop templates
    with open("template/add_item.html", "r") as f:
        ADD_ITEM_TEMPLATE = f.read()

    with open("template/add_mission.html", "r") as f:
        ADD_MISSION_TEMPLATE = f.read()

    with open("template/admin.receipts.html", "r") as f:
        ADMIN_RECEIPTS_TEMPLATE = f.read()

    with open("template/missions.html", "r") as f:
        MISSIONS_TEMPLATE = f.read()

    with open("template/modify_stock.html", "r") as f:
        MODIFY_STOCKS_TEMPLATE = f.read()

    with open("template/store.html", "r") as f:
        STORE_TEMPLATE = f.read()
except FileNotFoundError:
    abort(404, description="HTML Templates not found")
except Exception:
    abort(500, description="HTML Templates failed to load")

# ------------------------- MAIN APP ------------------------- #

# Run the app
if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=5000)

# --------------------------- END ---------------------------- #
