from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length, Optional, ValidationError
from decimal import Decimal
import re


class ProductForm(FlaskForm):
    name = StringField('Product Name',
                       validators=[
                           DataRequired(message="Product name is required"),
                           Length(min=2, max=100, message="Product name must be between 2 and 100 characters")
                       ],
                       render_kw={"placeholder": "Enter product name", "class": "form-control"})

    description = TextAreaField('Description',
                                validators=[
                                    Optional(),
                                    Length(max=1000, message="Description cannot exceed 1000 characters")
                                ],
                                render_kw={"placeholder": "Enter product description", "class": "form-control",
                                           "rows": "4"})

    price = DecimalField('Price (₹)',
                         validators=[
                             DataRequired(message="Price is required"),
                             NumberRange(min=0.01, max=999999.99, message="Price must be between ₹0.01 and ₹999,999.99")
                         ],
                         render_kw={"placeholder": "0.00", "class": "form-control", "step": "0.01"})

    stock = IntegerField('Stock Quantity',
                         validators=[
                             DataRequired(message="Stock quantity is required"),
                             NumberRange(min=0, max=999999, message="Stock must be between 0 and 999,999")
                         ],
                         render_kw={"placeholder": "0", "class": "form-control"})

    image_url = StringField('Image URL',
                            validators=[
                                Optional(),
                                Length(max=500, message="Image URL cannot exceed 500 characters")
                            ],
                            render_kw={"placeholder": "https://example.com/image.jpg", "class": "form-control"})

    # Alternative file upload field (if you want to handle file uploads)
    image_file = FileField('Upload Image',
                           validators=[
                               FileAllowed(['jpg', 'png', 'jpeg', 'gif', 'webp'],
                                           'Only image files are allowed (jpg, png, jpeg, gif, webp)')
                           ],
                           render_kw={"class": "form-control", "accept": "image/*"})

    is_active = BooleanField('Active Product',
                             default=True,
                             render_kw={"class": "form-check-input"})

    submit = SubmitField('Add Product', render_kw={"class": "btn btn-primary"})

    def validate_price(self, field):
        """Custom validation for price field"""
        if field.data:
            try:
                # Convert to Decimal for precise validation
                price_decimal = Decimal(str(field.data))
                if price_decimal.as_tuple().exponent < -2:
                    raise ValidationError('Price cannot have more than 2 decimal places')
            except (ValueError, TypeError):
                raise ValidationError('Invalid price format')

    def validate_image_url(self, field):
        """Custom validation for image URL"""
        if field.data:
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)

            if not url_pattern.match(field.data):
                raise ValidationError('Please enter a valid URL')


class EditProductForm(ProductForm):
    """Form for editing existing products"""
    submit = SubmitField('Update Product', render_kw={"class": "btn btn-success"})


class BulkUploadForm(FlaskForm):
    """Form for bulk product upload via CSV"""
    csv_file = FileField('Upload CSV File',
                         validators=[
                             DataRequired(message="Please select a CSV file"),
                             FileAllowed(['csv'], 'Only CSV files are allowed')
                         ],
                         render_kw={"class": "form-control", "accept": ".csv"})

    submit = SubmitField('Upload Products', render_kw={"class": "btn btn-info"})


class ProductSearchForm(FlaskForm):
    """Form for searching/filtering products"""
    search_query = StringField('Search Products',
                               validators=[Optional()],
                               render_kw={"placeholder": "Search by name or description", "class": "form-control"})

    min_price = DecimalField('Min Price',
                             validators=[Optional(), NumberRange(min=0)],
                             render_kw={"placeholder": "0.00", "class": "form-control", "step": "0.01"})

    max_price = DecimalField('Max Price',
                             validators=[Optional(), NumberRange(min=0)],
                             render_kw={"placeholder": "999999.99", "class": "form-control", "step": "0.01"})

    in_stock_only = BooleanField('In Stock Only', render_kw={"class": "form-check-input"})
    active_only = BooleanField('Active Only', default=True, render_kw={"class": "form-check-input"})

    submit = SubmitField('Search', render_kw={"class": "btn btn-outline-primary"})