import os
import threading
from collections import defaultdict
from flask import Flask, session, request, redirect, url_for, flash, render_template
from werkzeug.utils import secure_filename
import csv
import requests
import json
from dotenv import load_dotenv

# Load .env file
load_dotenv()

processing_status = False

# Set the URL and API key from the environment variables
API_URL = os.getenv('url')
API_KEY = os.getenv('key')
APP_SECRET_KEY = os.getenv('secret_key')

app = Flask(__name__)
app.secret_key = APP_SECRET_KEY

# Set the path to the upload folder
app.config['UPLOAD_FOLDER'] = 'uploads'

# Define the headers for API calls
headers = {
    'Content-Type': 'application/vnd.api+json',
    'X-CloudCart-ApiKey': API_KEY
}



def generate_image_urls(sku):
    base_url = "https://images.asics.com/is/image/asics/"
    image_suffixes = ["_SR_RT_GLB", "_SB_FR_GLB", "_SB_FL_GLB", "_SR_LT_GLB", "_SB_BK_GLB", "_SB_TP_GLB", "_SB_BT_GLB"]
    double_checks = ["", "-1", "-2"]
    zoom = "?$zoom$"
    sku = sku.replace('..', '_')  # replace ".." with "_"

    urls = []
    for suffix in image_suffixes:
        success = False
        for double_check in double_checks:
            url = f"{base_url}{sku}{suffix}{double_check}{zoom}"
            if get_response_code(url) == 200:
                urls.append(url)
                success = True
                break  # Break out of the inner loop if successful
        if not success:
            print(f"Failed to find a valid URL for SKU: {sku} with suffix: {suffix}")
    return urls



def get_response_code(url):
    try:
        response = requests.head(url, timeout=5)
        return response.status_code
    except requests.exceptions.RequestException:
        return None

def process_file(file_path):
    global processing_status

    # Create a dictionary to store SKU and their associated image URLs
    sku_to_images = defaultdict(list)

    # Open CSV file and generate image urls
    with open(file_path, 'r') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip the header
        for row in reader:
            sku = row[0]
            image_urls = generate_image_urls(sku)
            sku_to_images[sku].extend(image_urls)

    # For each SKU, check if images already exist and if not, upload all images and associate them with each variant
    for index, sku in enumerate(sku_to_images, start=1):
        print(f'Processing SKU {index}: {sku}')

        # GET variant IDs, item_id, and existing images
        response = requests.get(f'{API_URL}/api/v2/variants?filter[sku]={sku}&include=images', headers=headers)

        data = response.json()

        if data['data']:
            variant_ids = [item.get('id', None) for item in data['data']]
            item_id = data['data'][0]['attributes'].get('item_id', None)
            existing_images = data['data'][0]['relationships']['images']['data']
            if existing_images:
                print(f"Images already exist for SKU: {sku}, skipping...")
                continue
        else:
            print(f"No data found for SKU: {sku}")
            continue  # Skip to the next SKU

        # If images already exist for this SKU, skip to the next SKU
        if existing_images:
            continue

        image_ids = []
        # For each image URL of the SKU, upload the image
        for image_url in sku_to_images[sku]:

            # POST image
            image_data = {
                'data': {
                    'type': 'images',
                    'attributes': {
                        'src': image_url
                    },
                    'relationships': {
                        'product': {
                            'data': {
                                'type': 'products',
                                'id': str(item_id)
                            }
                        }
                    }
                }
            }
            image_response = requests.post(f'{API_URL}/api/v2/images', headers=headers, data=json.dumps(image_data))
            image_id = image_response.json()['data']['id']

            image_ids.append(image_id)

        # PATCH each variant with all images
        for variant_id in variant_ids:
            variant_data = {
                'data': {
                    'type': 'variants',
                    'id': variant_id,
                    'relationships': {
                        'images': {
                            'data': [{'type': 'images', 'id': id_} for id_ in image_ids]
                        }
                    }
                }
            }
            requests.patch(f'{API_URL}/api/v2/variants/{variant_id}', headers=headers, data=json.dumps(variant_data))
            print(f'Images with ids {image_ids} associated with variant {variant_id}')
    os.remove(file_path)
    processing_status = False

# After starting the thread, set a flag in the session
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    global processing_status
    if request.method == 'POST':
        file = request.files['file']
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        threading.Thread(target=process_file, args=(file_path,)).start()
        processing_status = True
        return redirect(url_for('processing_status'))
    return render_template('upload.html')

@app.route('/status')
def processing_status():
    global processing_status
    if processing_status:
        status = "The process has been started!"
    else:
        status = "The process has been completed!"
    return render_template('status.html', status=status)


if __name__ == '__main__':
    app.run(debug=True)