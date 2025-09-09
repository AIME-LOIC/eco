from flask import Flask, render_template, request, redirect, url_for, session
from supabase import create_client, Client
from werkzeug.utils import secure_filename
import os
import qrcode
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"

# --- Supabase config ---
SUPABASE_URL = "https://hdzblqzidgwaqbaqyyaz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhkemJscXppZGd3YXFiYXF5eWF6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc0MjIxNTYsImV4cCI6MjA3Mjk5ODE1Nn0.G2cXOescsoOej5eNzrJzTkVCyjpbVPNhx8UeXM_HPrA"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------- HELPER FUNCTIONS -----------------
def get_notifications():
    return session.get("notifications", [])

def add_notification(msg):
    notes = session.get("notifications", [])
    notes.append(msg)
    session["notifications"] = notes

def clear_notifications():
    session["notifications"] = []

# ----------------- ROUTES -----------------
@app.route("/")
def root():
    return redirect(url_for("welcome"))

@app.route("/welcome")
def welcome():
    return render_template("welcome.html")

@app.route("/choose")
def choose_role():
    role = request.args.get("role")
    if role == "buyer":
        return redirect(url_for("buyer_home"))
    elif role == "seller":
        return redirect(url_for("seller_login"))
    return redirect(url_for("welcome"))

# ----------------- SELLER -----------------
@app.route("/seller_register", methods=["GET", "POST"])
def seller_register():
    error = None
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        if not (name and email and phone and password):
            error = "All fields are required."
        else:
            try:
                existing = supabase.table("sellers").select("*").eq("email", email).execute()
                if existing.data and len(existing.data) > 0:
                    error = "Email already registered."
                else:
                    image_url = url_for("static", filename="images/default-profile.png")
                    supabase.table("sellers").insert({
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "password": password,
                        "role": "Seller",
                        "image_url": image_url
                    }).execute()
                    session["seller_logged_in"] = True
                    session["seller_email"] = email
                    return redirect(url_for("dashboard"))
            except Exception as e:
                print("Supabase error:", e)
                error = "Registration failed. Try again later."
    return render_template("seller_register.html", error=error)

@app.route("/seller_login", methods=["GET", "POST"])
def seller_login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            result = supabase.table("sellers").select("*").eq("email", email).execute()
            seller = result.data[0] if result.data else None
            if seller and seller.get("password") == password:
                session["seller_logged_in"] = True
                session["seller_email"] = email
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid email or password."
        except Exception as e:
            print("Supabase error:", e)
            error = "Login failed. Try again later."
    return render_template("seller_login.html", error=error)

@app.route("/dashboard")
def dashboard():
    if not session.get("seller_logged_in"):
        return redirect(url_for("seller_login"))
    email = session.get("seller_email")
    notifications = get_notifications()
    clear_notifications()
    total_sales = 0
    delivered_orders = 0
    pending_orders = 0
    best_selling = {}
    try:
        orders_result = supabase.table("orders").select("*").eq("seller_email", email).execute()
        orders = orders_result.data or []
        for o in orders:
            qty = int(o.get("quantity", 1))
            total_sales += qty
            if o.get("delivered"):
                delivered_orders += 1
            else:
                pending_orders += 1
            pname = o.get("product_name")
            if pname:
                best_selling[pname] = best_selling.get(pname, 0) + qty
    except Exception as e:
        print("Supabase error:", e)
    best_selling_products = sorted(best_selling.items(), key=lambda x: x[1], reverse=True)[:3]
    return render_template(
        "dashboard.html",
        notifications=notifications,
        total_sales=total_sales,
        delivered_orders=delivered_orders,
        pending_orders=pending_orders,
        best_selling_products=best_selling_products
    )

@app.route("/add_product", methods=["POST"])
def add_product():
    if not session.get("seller_logged_in"):
        return redirect(url_for("seller_login"))
    email = session.get("seller_email")
    pname = request.form.get("product_name")
    price = request.form.get("product_price")
    stock = int(request.form.get("stock", 0))
    image_file = request.files.get("product_image")
    image_name = None
    if image_file:
        os.makedirs("static/images", exist_ok=True)
        image_name = secure_filename(image_file.filename)
        image_file.save(os.path.join("static/images", image_name))
    try:
        supabase.table("products").insert({
            "product_name": pname,
            "product_price": price,
            "stock": stock,
            "seller_email": email,
            "image_path": image_name
        }).execute()
    except Exception as e:
        print("Supabase error:", e)
    return redirect(url_for("get_products"))

@app.route("/add")
def get_products():
    if not session.get("seller_logged_in"):
        return redirect(url_for("seller_login"))
    email = session.get("seller_email")
    products = []
    try:
        result = supabase.table("products").select("*").eq("seller_email", email).execute()
        products = result.data or []
    except Exception as e:
        print("Supabase error:", e)
    return render_template("add.html", data=products)

# ----------------- BUYER -----------------
@app.route("/buyer_home")
def buyer_home():
    try:
        products = supabase.table("products").select("*").execute().data or []
    except Exception as e:
        print("Supabase error:", e)
        products = []
    return render_template("buyer_home.html", products=products)

@app.route("/buy/<int:product_id>", methods=["POST"])
def buy_product(product_id):
    buyer_name = request.form.get("name")
    buyer_email = request.form.get("email")
    buyer_phone = request.form.get("phone")
    buyer_address = request.form.get("address")
    quantity = int(request.form.get("quantity", 1))
    try:
        product_result = supabase.table("products").select("*").eq("id", product_id).execute()
        product = product_result.data[0] if product_result.data else None
        if not product:
            return "Product not found", 404
        supabase.table("orders").insert({
            "product_name": product["product_name"],
            "product_price": product["product_price"],
            "quantity": quantity,
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "buyer_phone": buyer_phone,
            "buyer_address": buyer_address,
            "seller_email": product["seller_email"],
            "image_path": product.get("image_path")
        }).execute()
        return redirect(url_for("buyer_home"))
    except Exception as e:
        print("Supabase error:", e)
        return "Failed to place order", 500

# ----------------- LOGOUT -----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("welcome"))

# ----------------- RUN APP -----------------
if __name__ == "__main__":
    app.run(debug=True, port=2008)
