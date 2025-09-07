import os
import io
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
from flask_migrate import Migrate
from models import db, Product

app = Flask(__name__)

# إعدادات
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///motor_shop.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

db.init_app(app)
migrate = Migrate(app, db)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        try:
            name = request.form["name"]
            category = request.form["category"]
            price = float(request.form["price"])
            quantity = int(request.form["quantity"])
            db.session.add(Product(name=name, category=category, price=price, quantity=quantity))
            db.session.commit()
            flash("✅ تمت إضافة المنتج بنجاح", "success")
            return redirect(url_for("add_product"))
        except Exception as e:
            db.session.rollback()
            flash(f"❌ خطأ: {e}", "danger")
    return render_template("add_product.html")

@app.route("/reports", methods=["GET", "POST"])
def reports():
    name = request.form.get("name", "") if request.method == "POST" else ""
    category = request.form.get("category", "") if request.method == "POST" else ""
    min_price = request.form.get("min_price", 0, type=float) if request.method == "POST" else 0

    query = Product.query
    if min_price:
        query = query.filter(Product.price >= min_price)
    if name:
        query = query.filter(Product.name.ilike(f"%{name}%"))
    if category:
        query = query.filter(Product.category.ilike(f"%{category}%"))

    rows = query.all()
    total_price = sum(p.price for p in rows)
    total_quantity = sum(p.quantity for p in rows)

    return render_template("reports.html", rows=rows, total_price=total_price,
                           total_quantity=total_quantity,
                           filters={"name": name, "category": category, "min_price": min_price})

@app.route("/export", methods=["POST"])
def export():
    name = request.form.get("name", "")
    category = request.form.get("category", "")
    min_price = request.form.get("min_price", 0, type=float)

    query = Product.query
    if min_price:
        query = query.filter(Product.price >= min_price)
    if name:
        query = query.filter(Product.name.ilike(f"%{name}%"))
    if category:
        query = query.filter(Product.category.ilike(f"%{category}%"))

    df = pd.DataFrame([p.to_dict() for p in query.all()])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        (df if not df.empty else pd.DataFrame(columns=["ID","Name","Category","Price","Quantity"]))\
            .to_excel(writer, index=False, sheet_name="Report")
    output.seek(0)
    return send_file(output, download_name="report.xlsx", as_attachment=True)

@app.route("/import", methods=["POST"])
def import_excel():
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400
    try:
        df = pd.read_excel(file)
        required = {"Name","Category","Price","Quantity"}
        if not required.issubset(set(df.columns)):
            return jsonify({"ok": False, "error": f"Missing columns. Required: {sorted(required)}"}), 400
        created = 0
        for _, r in df.iterrows():
            db.session.add(Product(
                name=str(r["Name"]).strip(),
                category=str(r["Category"]).strip(),
                price=float(r["Price"]),
                quantity=int(r["Quantity"])
            ))
            created += 1
        db.session.commit()
        return jsonify({"ok": True, "created": created})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/products")
def api_products():
    q = Product.query
    name = request.args.get("name")
    category = request.args.get("category")
    min_price = request.args.get("min_price", type=float)
    if min_price is not None:
        q = q.filter(Product.price >= min_price)
    if name:
        q = q.filter(Product.name.ilike(f"%{name}%"))
    if category:
        q = q.filter(Product.category.ilike(f"%{category}%"))
    return jsonify([p.to_dict() for p in q.all()])

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
