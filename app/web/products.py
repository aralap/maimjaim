from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.services import ProductService
from app.services.exceptions import InventoryError
from app.web.decorators import admin_required, approved_required

bp = Blueprint("web_products", __name__, url_prefix="/products")


@bp.route("/")
@approved_required
def list_products():
    category_id = request.args.get("category_id", type=int)
    show_inactive = request.args.get("show_inactive") == "1"
    products = ProductService.list_products(
        active_only=not show_inactive,
        category_id=category_id,
    )
    categories = ProductService.list_categories()
    return render_template(
        "products/list.html",
        products=products,
        categories=categories,
        current_category_id=category_id,
        show_inactive=show_inactive,
    )


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def new_product():
    categories = ProductService.list_categories()
    if request.method == "POST":
        try:
            ProductService.create_product(
                name=request.form["name"],
                description=request.form.get("description") or None,
                sku=request.form["sku"].strip().upper(),
                price_cents=int(float(request.form.get("price", 0)) * 100),
                cost_cents=int(float(request.form.get("cost", 0)) * 100),
                initial_stock=int(request.form.get("initial_stock", 0)),
                reorder_point=int(request.form.get("reorder_point", 0)),
                category_id=int(request.form["category_id"]) if request.form.get("category_id") else None,
                unit=request.form.get("unit") or None,
                supplier=request.form.get("supplier") or None,
                user_id=current_user.id,
            )
            flash("Producto creado.", "success")
            return redirect(url_for("web_products.list_products"))
        except (InventoryError, ValueError) as exc:
            flash(str(exc), "error")

    return render_template("products/new.html", categories=categories)


@bp.route("/<int:product_id>")
@approved_required
def detail(product_id):
    product = ProductService.get_product(product_id)
    if not product:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("web_products.list_products"))
    return render_template("products/detail.html", product=product)


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    product = ProductService.get_product(product_id)
    if not product:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("web_products.list_products"))

    categories = ProductService.list_categories()
    if request.method == "POST":
        try:
            ProductService.update_product(
                product_id,
                name=request.form["name"],
                description=request.form.get("description") or None,
                category_id=int(request.form["category_id"]) if request.form.get("category_id") else None,
                unit=request.form.get("unit") or None,
                supplier=request.form.get("supplier") or None,
                user_id=current_user.id,
            )
            flash("Producto actualizado.", "success")
            return redirect(url_for("web_products.detail", product_id=product_id))
        except (InventoryError, ValueError) as exc:
            flash(str(exc), "error")

    return render_template(
        "products/edit.html",
        product=product,
        categories=categories,
    )


@bp.route("/<int:product_id>/deactivate", methods=["POST"])
@admin_required
def deactivate(product_id):
    try:
        product = ProductService.deactivate_product(product_id, user_id=current_user.id)
        flash(f"Producto {product.name} desactivado.", "success")
    except InventoryError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_products.detail", product_id=product_id))


@bp.route("/<int:product_id>/activate", methods=["POST"])
@admin_required
def activate(product_id):
    try:
        product = ProductService.activate_product(product_id, user_id=current_user.id)
        flash(f"Producto {product.name} reactivado.", "success")
    except InventoryError as exc:
        flash(str(exc), "error")
    return redirect(url_for("web_products.detail", product_id=product_id))


@bp.route("/<int:product_id>/variants/new", methods=["GET", "POST"])
@admin_required
def new_variant(product_id):
    product = ProductService.get_product(product_id)
    if not product:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("web_products.list_products"))

    if request.method == "POST":
        try:
            attrs = {}
            if request.form.get("size"):
                attrs["size"] = request.form["size"]
            if request.form.get("color"):
                attrs["color"] = request.form["color"]

            ProductService.add_variant(
                product_id,
                sku=request.form["sku"].strip().upper(),
                price_cents=int(float(request.form.get("price", 0)) * 100),
                cost_cents=int(float(request.form.get("cost", 0)) * 100),
                attributes=attrs,
                initial_stock=int(request.form.get("initial_stock", 0)),
                reorder_point=int(request.form.get("reorder_point", 0)),
                user_id=current_user.id,
            )
            flash("Variante agregada.", "success")
            return redirect(url_for("web_products.detail", product_id=product_id))
        except (InventoryError, ValueError) as exc:
            flash(str(exc), "error")

    return render_template("products/new_variant.html", product=product)
