from flask import Flask, request, render_template, session
import pandas as pd
import random
from flask_sqlalchemy import SQLAlchemy
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# load files===========================================================================================================
trending_products = pd.read_csv("trending_products.csv")
train_data = pd.read_csv("clean_data.csv")

# database configuration---------------------------------------
app.secret_key = "aDHEK983UJNd93jdidKLdy6429"
 #app.config['SQLALCHEMY_DATABASE_URI'] = "mysql://root:@localhost/ecom"
 #app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
 #db = SQLAlchemy(app)


# Define your model class for the 'signup' table
# class Signup(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(100), nullable=False)
#     email = db.Column(db.String(100), nullable=False)
#     password = db.Column(db.String(100), nullable=False)

# Define your model class for the 'signup' table
# class Signin(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(100), nullable=False)
#     password = db.Column(db.String(100), nullable=False)


# Recommendations functions============================================================================================
# Function to truncate product name
def truncate(text, length):
    if len(text) > length:
        return text[:length] + "..."
    else:
        return text


def filter_trending_products(trending_products, interested_products):
    """
    Filter trending products to show only those similar to interested products.
    If no interested products, return all trending products.
    Similarity based on brand match or name keyword match.
    """
    if not interested_products or len(interested_products) == 0:
        return trending_products
    
    # Collect brands and name keywords from interested products
    interested_brands = set()
    interested_keywords = set()
    for product in interested_products:
        if 'brand' in product and product['brand']:
            brand = product['brand'].lower().strip().replace(',', ' ').replace('  ', ' ')
            interested_brands.add(brand)
            # Add brand words to keywords, cleaning commas
            brand_words = brand.split()
            interested_keywords.update(brand_words)
        if 'name' in product and product['name']:
            # Split name into keywords, cleaning punctuation
            name_words = product['name'].lower().replace(',', ' ').replace('-', ' ').replace('  ', ' ').split()
            interested_keywords.update(name_words)
    
    if not interested_brands and not interested_keywords:
        return trending_products
    
    # Filter trending products
    filtered_indices = set()
    
    for idx, row in trending_products.iterrows():
        trending_brand = str(row['Brand']).lower().strip().replace(',', ' ').replace('  ', ' ') if pd.notna(row['Brand']) else ''
        trending_name = str(row['Name']).lower().replace(',', ' ').replace('-', ' ').replace('  ', ' ') if pd.notna(row['Name']) else ''
        
        # Check brand match
        if trending_brand in interested_brands:
            filtered_indices.add(idx)
            continue
        
        # Check name keyword match (at least 1 matching keyword)
        name_words = set(trending_name.split())
        matching_keywords = interested_keywords.intersection(name_words)
        if len(matching_keywords) >= 1:
            filtered_indices.add(idx)
    
    if filtered_indices:
        filtered = trending_products.loc[list(filtered_indices)]
        return filtered.drop_duplicates()
    else:
        # If no matches, return original trending products
        return trending_products


def content_based_recommendations(train_data, item_name, top_n=10, interested_products=None):
    """
    Recommend products based on keyword search and interested products.
    Returns products that match the search query, not random items.
    """
    if not item_name or item_name.strip() == '':
        return pd.DataFrame()

    # Convert search query to lowercase for case-insensitive matching
    search_query = str(item_name).lower().strip()
    
    # Create a case-insensitive copy of product names for matching
    train_data_copy = train_data.copy()
    train_data_copy['Name_lower'] = train_data_copy['Name'].str.lower()
    
    # First, try exact match or direct keyword match in product names
    relevant_items = train_data_copy[train_data_copy['Name_lower'].str.contains(search_query, case=False, na=False)]
    
    # If no exact matches found, try searching by individual keywords
    if len(relevant_items) == 0:
        # Split the search query into keywords
        keywords = search_query.split()
        
        # Find products that contain any of these keywords
        mask = pd.Series([False] * len(train_data_copy))
        for keyword in keywords:
            if len(keyword) > 2:  # Only search with keywords longer than 2 chars
                mask |= train_data_copy['Name_lower'].str.contains(keyword, case=False, na=False)
        
        relevant_items = train_data_copy[mask]
    
    # If still no results, perform a broader brand-based or category search
    if len(relevant_items) == 0:
        # Try searching in brand names
        relevant_items = train_data_copy[train_data_copy['Brand'].str.lower().str.contains(search_query, case=False, na=False)]
    
    # Remove duplicates
    relevant_items = relevant_items.drop_duplicates(subset='Name')
    
    # Boost recommendations based on interested products
    if interested_products and len(relevant_items) > 0:
        boosted_indices = []
        for interested in interested_products:
            interested_brand = interested.get('brand', '').lower()
            interested_name = interested.get('name', '').lower()
            
            # Find items that match the interested product's brand
            brand_matches = relevant_items[relevant_items['Brand'].str.lower().str.contains(interested_brand, case=False, na=False)]
            boosted_indices.extend(brand_matches.index.tolist())
        
        # Prioritize boosted items
        if boosted_indices:
            boosted_df = relevant_items.loc[boosted_indices].drop_duplicates()
            non_boosted_df = relevant_items[~relevant_items.index.isin(boosted_indices)]
            relevant_items = pd.concat([boosted_df, non_boosted_df])
    
    # Return the top N relevant items
    if len(relevant_items) > 0:
        result_items = relevant_items.head(top_n)[['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']]
        return result_items
    else:
        # If absolutely nothing matches, return empty dataframe
        print(f"No products found matching '{item_name}'")
        return pd.DataFrame()
# routes===============================================================================
# List of predefined image URLs
random_image_urls = [
    "/static/img/img_1.png",
    "/static/img/img_2.png",
    "/static/img/img_3.png",
    "/static/img/img_4.png",
    "/static/img/img_5.png",
    "/static/img/img_6.png",
    "/static/img/img_7.png",
    "/static/img/img_8.png",
]


@app.route("/")
def index():
    # Get interested products from session
    interested_products = session.get('interested_products', [])
    
    if interested_products:
        # Get brands from interested products
        interested_brands = set()
        for p in interested_products:
            if 'brand' in p and p['brand']:
                brand = p['brand'].lower().strip().replace(',', ' ')
                interested_brands.add(brand)
        
        if interested_brands:
            # Find similar products from full dataset
            similar_mask = train_data['Brand'].str.lower().str.strip().str.replace(',', ' ').isin(interested_brands)
            similar_products = train_data[similar_mask][['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']].head(9)
            
            if len(similar_products) >= 9:
                display_products = similar_products
            else:
                # Fill with trending products to reach 9
                remaining = 9 - len(similar_products)
                trending_fill = trending_products.head(remaining)[['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']]
                display_products = pd.concat([similar_products, trending_fill]).drop_duplicates()
        else:
            display_products = trending_products.head(9)[['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']]
    else:
        display_products = trending_products.head(9)[['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']]
    
    # Create random image URLs
    random_product_image_urls = [random.choice(random_image_urls) for _ in range(len(display_products))]
    price = [40, 50, 60, 70, 100, 122, 106, 50, 30, 50]
    return render_template('index.html', trending_products=display_products, truncate=truncate,
                           random_product_image_urls=random_product_image_urls,
                           random_price=random.choice(price))

@app.route("/update_interested", methods=['POST'])
def update_interested():
    interested_products = request.get_json()
    session['interested_products'] = interested_products
    return {'status': 'success'}

@app.route("/main")
def main():
    empty_df = pd.DataFrame()
    return render_template('main.html', content_based_rec=empty_df)

# routes
@app.route("/index")
def indexredirect():
    # Get interested products from session
    interested_products = session.get('interested_products', [])
    
    if interested_products:
        # Get brands from interested products
        interested_brands = set()
        for p in interested_products:
            if 'brand' in p and p['brand']:
                brand = p['brand'].lower().strip().replace(',', ' ')
                interested_brands.add(brand)
        
        if interested_brands:
            # Find similar products from full dataset
            similar_mask = train_data['Brand'].str.lower().str.strip().str.replace(',', ' ').isin(interested_brands)
            similar_products = train_data[similar_mask][['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']].head(9)
            
            if len(similar_products) >= 9:
                display_products = similar_products
            else:
                # Fill with trending products to reach 9
                remaining = 9 - len(similar_products)
                trending_fill = trending_products.head(remaining)[['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']]
                display_products = pd.concat([similar_products, trending_fill]).drop_duplicates()
        else:
            display_products = trending_products.head(9)[['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']]
    else:
        display_products = trending_products.head(9)[['Name', 'ReviewCount', 'Brand', 'ImageURL', 'Rating']]
    
    # Create random image URLs
    random_product_image_urls = [random.choice(random_image_urls) for _ in range(len(display_products))]
    price = [40, 50, 60, 70, 100, 122, 106, 50, 30, 50]
    return render_template('index.html', trending_products=display_products, truncate=truncate,
                           random_product_image_urls=random_product_image_urls,
                           random_price=random.choice(price))

# @app.route("/signup", methods=['POST','GET'])
# def signup():
#     if request.method=='POST':
#         username = request.form['username']
#         email = request.form['email']
#         password = request.form['password']

#         new_signup = Signup(username=username, email=email, password=password)
#         db.session.add(new_signup)
#         db.session.commit()

#         # Create a list of random image URLs for each product
#         random_product_image_urls = [random.choice(random_image_urls) for _ in range(len(trending_products))]
#         price = [40, 50, 60, 70, 100, 122, 106, 50, 30, 50]
#         return render_template('index.html', trending_products=trending_products.head(8), truncate=truncate,
#                                random_product_image_urls=random_product_image_urls, random_price=random.choice(price),
#                                signup_message='User signed up successfully!'
#                                )

# Route for signup page
# @app.route('/signin', methods=['POST', 'GET'])
# def signin():
#     if request.method == 'POST':
#         username = request.form['signinUsername']
#         password = request.form['signinPassword']
#         new_signup = Signin(username=username,password=password)
#         db.session.add(new_signup)
#         db.session.commit()

#         # Create a list of random image URLs for each product
#         random_product_image_urls = [random.choice(random_image_urls) for _ in range(len(trending_products))]
#         price = [40, 50, 60, 70, 100, 122, 106, 50, 30, 50]
#         return render_template('index.html', trending_products=trending_products.head(8), truncate=truncate,
#                                random_product_image_urls=random_product_image_urls, random_price=random.choice(price),
#                                signup_message='User signed in successfully!'
#                                )
@app.route("/recommendations", methods=['POST', 'GET'])
def recommendations():
    empty_df = pd.DataFrame()   # create empty dataframe

    if request.method == 'POST':
        prod = request.form.get('prod')
        nbr = int(request.form.get('nbr'))
        interested_products = request.form.get('interested_products', '')

        # Parse interested products (JSON string from frontend)
        interested_list = []
        if interested_products:
            try:
                import json
                interested_list = json.loads(interested_products)
            except:
                interested_list = []

        # Store interested products in session
        session['interested_products'] = interested_list

        content_based_rec = content_based_recommendations(train_data, prod, top_n=nbr, interested_products=interested_list)

        if content_based_rec.empty:
            message = f"No products found matching '{prod}'. Please try searching for a different product type."
            return render_template(
                'main.html',
                message=message,
                content_based_rec=empty_df
            )
        else:
            price = [40, 50, 60, 70, 100, 122, 106, 50, 30, 50]
            return render_template(
                'main.html',
                content_based_rec=content_based_rec,
                truncate=truncate,
                random_price=random.choice(price),
                interested_products=interested_list
            )


if __name__=='__main__':
    app.run(debug=True)