# Shop Platform (For hackathons)

This project is a Shopping platform built using Python and Flask for hackathons (Specifically Scrapyard).
It's derived from Scrapyard Bounty (Sharjah), 

## Features

- User authentication and session management
- Full Shop Features
  - Setting up items and stock
  - Admin Panel
  - Buying and receipt management and more
- Simple RESTful API
- Vercel Support

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/DefinetlyNotAI/Scrapyard_Bounty.git
    cd ctf-platform
    ```

2. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Modify the scripts environment variables to your secrets

## Usage

1. Run the Flask application:
    ```sh
    python CTF.py
    ```

2. Open your web browser and navigate to `http://127.0.0.1:5000`.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License.


---

# API Documentation

This document provides a detailed overview of the available API endpoints for the project.
Each endpoint includes information on the HTTP method, URL, required parameters,
and whether admin access is required as well as rate limits.

> [!IMPORTANT]
> Keep the `accept_mimetypes` as "*/*" in the request headers to receive JSON error responses.
> The API is designed to return HTML responses by default if errors occur.

---

### `executeQuery`

- **URL:** `/api/executeQuery`
- **Method:** POST
- **Description:** Executes a SQL query on the database.
- **Admin?:** 🔐
- **Rate Limit:** 🚀
- **Plug and Play?:** ❌ (Requires an HTTP request with a JSON payload)
- **Request Body Preview:**
  ```json
  {
    "query": "SELECT * FROM users"
  }
  ```
- **Response preview**
    - `#200`:
       ```json
       {
         "id": 1,
         "username": "example_user",
         "email": "user@example.com"
       }
       ```
    - `#400`:
       ```json
       {
         "error": "No query provided"
       }
       ```
    - `#500`:
       ```json
       {
         "error": "Query Execution Failed - API execute_query"
       }
       ```

---

### `api_status`

- **URL:** `/api/status`
- **Method:** GET
- **Description:** Checks if the API is running and verifies database connectivity.
- **Admin?:** 🔓
- **Rate Limit:** 🚀
- **Plug and Play?:** ✅
- **Response preview**
    - `#200`:
       ```json
       {
         "status": "API is running",
         "uptime_seconds": 12345.67,
         "database_connected": true
       }
       ```

---

### `buy`

- **URL:** `/api/shop/buy`
- **Method:** POST
- **Description:** Allows a user to buy an item from the shop, generating a receipt image if the item is in stock.
- **Admin?:** 🔓
- **Rate Limit:** 🔥 30 requests/hour
- **Plug and Play?:** ❌ (Proper JSON body must be sent)
- **Request Body Preview:**
  ```json
  {
    "item_id": "123",
    "email": "user@example.com"
  }
  ```
- **Response preview**
    - `#200`:
      ```json
      {
        "message": "Receipt generated successfully",
        "receipt_url": "path/to/receipt_image.png"
      }
      ```
    - `#400`:
      ```json
      {
        "message": "Invalid input! Make sure all fields are filled."
      }
      ```
    - `#404`:
      ```json
      {
        "message": "Item out of stock"
      }
      ```

---

### `update_stock`

- **URL:** `/api/shop/update_stock`
- **Method:** POST
- **Description:** Allows an admin to update the stock levels for items in the shop.
- **Admin?:** 🔐
- **Rate Limit:** 🚀
- **Plug and Play?:** ❌ (Admin required and Proper JSON body must be sent)
- **Request Body Preview:**
  ```json
  {
    "stock_123": "10",
    "stock_124": "5"
  }
  ```
- **Response preview**
    - `#200`:
      ```json
      {
        "message": "Stock updated successfully!"
      }
      ```
    - `#400`:
      ```json
      {
        "message": "Invalid stock values"
      }
      ```

---

### `cancel_receipt`

- **URL:** `/api/shop/cancel_receipt`
- **Method:** POST
- **Description:** Allows an admin to cancel a receipt by deleting it from the database.
- **Admin?:** 🔐
- **Rate Limit:** 🚀
- **Plug and Play?:** ❌ (Admin required and Proper JSON body must be sent)
- **Request Body Preview:**
  ```json
  {
    "receipt_id": "abc123"
  }
  ```
- **Response preview**
    - `#200`:
      ```json
      {
        "message": "Receipt cancelled!"
      }
      ```
    - `#400`:
      ```json
      {
        "message": "Receipt not found"
      }
      ```

---

### `remove_mission`

- **URL:** `/api/shop/remove_mission/<int:mission_id>`
- **Method:** GET
- **Description:** Allows an admin to remove a mission from the system.
- **Admin?:** 🔐
- **Rate Limit:** 🚀
- **Plug and Play?:** ✔️ (Admin required)
- **Response preview**
    - `#200`:
      ```json
      {
        "message": "Mission removed successfully!"
      }
      ```
    - `#404`:
      ```json
      {
        "message": "Mission not found"
      }
      ```

---

### `add_mission`

- **URL:** `/api/shop/add_mission`
- **Method:** GET, POST
- **Description:** Allows an admin to add a new mission to the system.
- **Admin?:** 🔐
- **Rate Limit:** 🚀
- **Plug and Play?:** ❌ (Admin required and Proper JSON body must be sent)
- **Request Body Preview:**
  ```json
  {
    "name": "New Mission",
    "description": "A description of the new mission",
    "scraps": "100"
  }
  ```
- **Response preview**
    - `#200`:
      ```json
      {
        "message": "Mission added successfully!"
      }
      ```
    - `#400`:
      ```json
      {
        "message": "All fields are required!"
      }
      ```

---

### Mini Table for Emoji Explanation

| Emoji | Sector        | Meaning                                                                             |
|-------|---------------|-------------------------------------------------------------------------------------|
| ❌     | Plug and Play | Impossible to use directly in the browser (requires proper HTTP requests)           |
| ✔️    | Plug and Play | Requires some setup (like being logged in or an admin) but still browser-accessible |
| ✅     | Plug and Play | Fully accessible via browser without any additional setup                           |
| 🔓    | Admin?        | No admin required to use the api                                                    |
| 🔐    | Admin?        | Admin is required to use the api                                                    |
| 🚀    | Rate Limit    | No rate limit                                                                       |

---
