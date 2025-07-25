from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from functools import wraps
import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
import io
import base64

# Import your models and forms
from models import db, Product, User, Order, OrderItem, OrderStatus
from forms import ProductForm, EditProductForm, BulkUploadForm, ProductSearchForm

# Create admin blueprint
admin = Blueprint('admin', __name__, url_prefix='/admin')


# Session-based login required decorator
def login_required(f):
    """Decorator to check if user is logged in"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('choose_login'))
        return f(*args, **kwargs)

    return decorated_function


# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('choose_login'))

        if not session['user'].get('is_admin'):
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)

    return decorated_function


# Admin dashboard
@admin.route('/')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with key metrics"""
    # Gather dashboard stats
    stats = {
        'total_products': Product.query.count(),
        'total_orders': Order.query.count(),
        'total_customers': User.query.count(),
        'pending_orders': Order.query.filter_by(status=OrderStatus.PENDING).count(),
        'low_stock_products': Product.query.filter(Product.stock < 10, Product.is_active == True).count(),
        'products': Product.query.order_by(Product.created_at.desc()).limit(10).all(),
        'orders': Order.query.order_by(Order.created_at.desc()).limit(10).all(),
        'customers': User.query.order_by(User.created_at.desc()).limit(10).all(),
    }
    return render_template('admin/admin_dashboard.html', stats=stats)


# Products management
@admin.route('/products')
@login_required
@admin_required
def products():
    """List all products with search/filter functionality"""
    form = ProductSearchForm()

    # Build query based on search filters
    query = Product.query

    if form.validate_on_submit():
        if form.search_query.data:
            search_term = f"%{form.search_query.data}%"
            query = query.filter(
                (Product.name.ilike(search_term)) |
                (Product.description.ilike(search_term))
            )

        if form.min_price.data:
            query = query.filter(Product.price >= form.min_price.data)

        if form.max_price.data:
            query = query.filter(Product.price <= form.max_price.data)

        if form.in_stock_only.data:
            query = query.filter(Product.stock > 0)

        if form.active_only.data:
            query = query.filter(Product.is_active == True)

    # Pagination
    page = request.args.get('page', 1, type=int)
    products = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('admin/products.html', products=products, form=form)


# Optional: Product detail page
@admin.route('/product/<int:product_id>')
def product_detail(product_id):
    """Individual product detail page"""
    product = Product.query.get_or_404(product_id)

    # Get related products (same category or similar)
    related_products = Product.query.filter(
        Product.is_active == True,
        Product.id != product_id
    ).limit(4).all()

    return render_template('product_detail.html',
                           product=product,
                           related_products=related_products)


@admin.route('/products/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    """Add new product"""
    form = ProductForm()

    if form.validate_on_submit():
        try:
            # Handle image upload
            image_url = form.image_url.data

            if form.image_file.data:
                # Save uploaded file
                image_url = save_product_image(form.image_file.data)

            # Create new product
            product = Product(
                name=form.name.data,
                description=form.description.data,
                price=form.price.data,
                stock=form.stock.data,
                image_url=image_url,
                is_active=form.is_active.data
            )

            db.session.add(product)
            db.session.commit()

            flash(f'Product "{product.name}" added successfully!', 'success')
            return redirect(url_for('admin.products'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error adding product: {str(e)}', 'error')

    return render_template('admin/add_product.html', form=form)




@admin.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    """Edit existing product"""
    product = Product.query.get_or_404(product_id)
    form = EditProductForm(obj=product)

    if form.validate_on_submit():
        try:
            # Handle image upload
            if form.image_file.data:
                # Delete old image if it exists
                if product.image_url:
                    delete_product_image(product.image_url)

                # Save new image
                product.image_url = save_product_image(form.image_file.data)
            elif form.image_url.data:
                product.image_url = form.image_url.data

            # Update product fields
            product.name = form.name.data
            product.description = form.description.data
            product.price = form.price.data
            product.stock = form.stock.data
            product.is_active = form.is_active.data

            db.session.commit()

            flash(f'Product "{product.name}" updated successfully!', 'success')
            return redirect(url_for('admin.products'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'error')

    return render_template('admin/edit_product.html', form=form, product=product)


@admin.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    """Delete product"""
    product = Product.query.get_or_404(product_id)

    try:
        # Check if product has any orders
        if product.order_items:
            flash('Cannot delete product with existing orders. Consider deactivating instead.', 'error')
            return redirect(url_for('admin.products'))

        # Delete product image
        if product.image_url:
            delete_product_image(product.image_url)

        db.session.delete(product)
        db.session.commit()

        flash(f'Product "{product.name}" deleted successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')

    return redirect(url_for('admin.products'))


@admin.route('/products/toggle-status/<int:product_id>', methods=['POST'])
@login_required
@admin_required
def toggle_product_status(product_id):
    """Toggle product active status"""
    product = Product.query.get_or_404(product_id)

    try:
        product.is_active = not product.is_active
        db.session.commit()

        status = "activated" if product.is_active else "deactivated"
        flash(f'Product "{product.name}" {status} successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating product status: {str(e)}', 'error')

    return redirect(url_for('admin.products'))


@admin.route('/products/bulk-upload', methods=['GET', 'POST'])
@login_required
@admin_required
def bulk_upload_products():
    """Bulk upload products from CSV"""
    form = BulkUploadForm()

    if form.validate_on_submit():
        try:
            import csv
            import io

            # Read CSV file
            csv_file = form.csv_file.data
            stream = io.StringIO(csv_file.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)

            products_added = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Validate required fields
                    if not all([row.get('name'), row.get('price'), row.get('stock')]):
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue

                    # Create product
                    product = Product(
                        name=row['name'].strip(),
                        description=row.get('description', '').strip(),
                        price=float(row['price']),
                        stock=int(row['stock']),
                        image_url=row.get('image_url', '').strip(),
                        is_active=row.get('is_active', 'true').lower() == 'true'
                    )

                    db.session.add(product)
                    products_added += 1

                except ValueError as e:
                    errors.append(f"Row {row_num}: Invalid data format - {str(e)}")
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

            db.session.commit()

            if products_added > 0:
                flash(f'Successfully added {products_added} products!', 'success')

            if errors:
                flash(f'Errors encountered: {"; ".join(errors[:5])}', 'error')

        except Exception as e:
            db.session.rollback()
            flash(f'Error processing CSV file: {str(e)}', 'error')

    return render_template('admin/bulk_upload.html', form=form)


def save_product_image(image_file):
    """Save uploaded image file and return URL"""
    if not image_file:
        return None

    # Generate unique filename
    filename = secure_filename(image_file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"

    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
    os.makedirs(upload_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(upload_dir, unique_filename)

    # Process image (resize if needed)
    try:
        with Image.open(image_file) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize if too large
            max_size = (800, 800)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save optimized image
            img.save(file_path, 'JPEG', quality=85, optimize=True)
    except Exception as e:
        # If image processing fails, save as is
        image_file.save(file_path)

    # Return URL path for the image
    return f"/static/uploads/products/{unique_filename}"


def delete_product_image(image_url):
    """Delete product image file"""
    if not image_url or not image_url.startswith('/static/uploads/products/'):
        return

    try:
        file_path = os.path.join(current_app.root_path, image_url.lstrip('/'))
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        current_app.logger.warning(f"Failed to delete image: {str(e)}")


# Orders management
@admin.route('/orders')
@login_required
@admin_required
def orders():
    """List all orders"""
    status_filter = request.args.get('status')
    page = request.args.get('page', 1, type=int)

    query = Order.query

    if status_filter:
        query = query.filter_by(status=OrderStatus(status_filter))

    orders = query.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('admin/orders.html', orders=orders, OrderStatus=OrderStatus)


@admin.route('/orders/<int:order_id>')
@login_required
@admin_required
def order_detail(order_id):
    """Order detail view"""
    order = Order.query.get_or_404(order_id)
    return render_template('admin/order_detail.html', order=order, OrderStatus=OrderStatus)


@admin.route('/orders/<int:order_id>/update-status', methods=['POST'])
@login_required
@admin_required
def update_order_status(order_id):
    """Update order status"""
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')

    try:
        if new_status in [status.value for status in OrderStatus]:
            order.update_status(OrderStatus(new_status))
            db.session.commit()
            flash(f'Order {order.order_number} status updated to {new_status}', 'success')
        else:
            flash('Invalid status', 'error')

    except Exception as e:
        db.session.rollback()
        flash(f'Error updating order status: {str(e)}', 'error')

    return redirect(url_for('admin.order_detail', order_id=order_id))


# Users management
@admin.route('/users')
@login_required
@admin_required
def users():
    """List all users"""
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/users.html', users=users)


@admin.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """User detail view"""
    user = User.query.get_or_404(user_id)
    user_orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
    return render_template('admin/user_detail.html', user=user, orders=user_orders)


# API endpoints for AJAX requests
@admin.route('/api/products/<int:product_id>')
@login_required
@admin_required
def api_product_detail(product_id):
    """Get product details as JSON"""
    product = Product.query.get_or_404(product_id)
    return jsonify(product.to_dict())


@admin.route('/api/products/<int:product_id>/stock', methods=['POST'])
@login_required
@admin_required
def api_update_stock(product_id):
    """Update product stock via API"""
    product = Product.query.get_or_404(product_id)

    try:
        new_stock = int(request.json.get('stock', 0))
        product.stock = new_stock
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Stock updated to {new_stock}',
            'stock': new_stock
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400


@admin.route('/api/dashboard-stats')
@login_required
@admin_required
def api_dashboard_stats():
    """Get dashboard statistics as JSON"""
    stats = {
        'total_products': Product.query.count(),
        'active_products': Product.query.filter_by(is_active=True).count(),
        'total_orders': Order.query.count(),
        'pending_orders': Order.query.filter_by(status=OrderStatus.PENDING).count(),
        'processing_orders': Order.query.filter_by(status=OrderStatus.PROCESSING).count(),
        'shipped_orders': Order.query.filter_by(status=OrderStatus.SHIPPED).count(),
        'delivered_orders': Order.query.filter_by(status=OrderStatus.DELIVERED).count(),
        'cancelled_orders': Order.query.filter_by(status=OrderStatus.CANCELLED).count(),
    }

    return jsonify(stats)


# Export functionality
@admin.route('/export/products')
@login_required
@admin_required
def export_products():
    """Export products to CSV"""
    import csv
    from flask import Response

    def generate():
        yield 'name,description,price,stock,image_url,is_active,created_at\n'

        products = Product.query.all()
        for product in products:
            yield f'"{product.name}","{product.description or ""}",{product.price},{product.stock},"{product.image_url or ""}",{product.is_active},"{product.created_at}"\n'

    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=products.csv'}
    )


@admin.route('/export/orders')
@login_required
@admin_required
def export_orders():
    """Export orders to CSV"""
    from flask import Response

    def generate():
        yield 'order_number,customer_name,customer_email,total_amount,status,created_at\n'

        orders = Order.query.all()
        for order in orders:
            yield f'"{order.order_number}","{order.customer_name}","{order.customer_email}",{order.total_amount},"{order.status.value}","{order.created_at}"\n'

    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=orders.csv'}
    )


# Error handlers for admin routes
@admin.errorhandler(404)
def admin_not_found(error):
    return render_template('admin/404.html'), 404


@admin.errorhandler(500)
def admin_internal_error(error):
    db.session.rollback()
    return render_template('admin/500.html'), 500