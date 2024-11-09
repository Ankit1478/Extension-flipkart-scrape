from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from openai import OpenAI
from pymongo import MongoClient
from bson import ObjectId 
from bson import ObjectId  

# MongoDB setup
MONGO_URI = ""
conn = MongoClient(MONGO_URI)
db = conn["scraped_data"] 
collection = db["data"]    

app = FastAPI()

client = OpenAI(api_key="")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://YOUR_EXTENSION_ID"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    url: str

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def scroll_to_bottom(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        for _ in range(0, last_height, 700):
            driver.execute_script(f"window.scrollTo(0, {_});")
            time.sleep(0.3)
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

def extract_product_info(product_element):
    product_data = {
        "name": "",
        "ratings": {
            "score": "",
            "total_ratings": "",
            "total_reviews": ""
        },
        "specifications": []
    }
    
    try:
        name_element = product_element.find_element(By.CLASS_NAME, "KzDlHZ")
        product_data["name"] = name_element.text
    except:
        print("Could not find product name")
        
    try:
        rating_score = product_element.find_element(By.CLASS_NAME, "XQDdHH")
        product_data["ratings"]["score"] = rating_score.text.strip()
        
        ratings_element = product_element.find_element(By.CLASS_NAME, "Wphh3N")
        ratings_text = ratings_element.text
        
        parts = ratings_text.split(" & ")
        if len(parts) == 2:
            ratings = parts[0].strip().split(" ")[0]
            reviews = parts[1].strip().split(" ")[0]
            product_data["ratings"]["total_ratings"] = ratings
            product_data["ratings"]["total_reviews"] = reviews
    except:
        print("Could not find ratings information")
        
    try:
        specs = product_element.find_elements(By.CSS_SELECTOR, ".G4BRas li")
        product_data["specifications"] = [spec.text for spec in specs]
    except:
        print("Could not find specifications")
        
    return product_data



def convert_object_ids(data):
    """
    Recursively convert ObjectId instances in dictionaries to strings.
    """
    if isinstance(data, dict):
        return {key: convert_object_ids(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_object_ids(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data

@app.post("/scrape")
async def scrape_products(request: ScrapeRequest):
    driver = setup_driver()
    all_products = []
    
    try:
        driver.get(request.url)
        time.sleep(2)
        
        scroll_to_bottom(driver)
        
        product_elements = driver.find_elements(By.CSS_SELECTOR, "div.col.col-7-12")
        
        for element in product_elements:
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            
            product_data = extract_product_info(element)
            if product_data["name"]:
                all_products.append(product_data)
                
                # Insert product data into MongoDB and capture the insert result
                insert_result = collection.insert_one(product_data)
                
                # Add the inserted document ID to product data as a string
                product_data["_id"] = str(insert_result.inserted_id)
        
        # Convert `all_products` to ensure any ObjectIds are strings
        all_products = convert_object_ids(all_products)

        products_text = "\n".join([f"{product['name']}: {product['specifications']}" for product in all_products if product['name']])
        
        completion = client.chat.completions.create(
            model="gpt-4o",  
            messages=[
                {"role": "user", "content": f"Here are some products and specifications:\n{products_text}. Can you summarize or provide additional insights for the frontend?"}
            ]
        )
        
        openai_response = completion.choices[0].message.content
        
        return {
            "total_products": len(all_products),
            "products": all_products,
            "openai_response": openai_response  
        }
            
    except Exception as e:
        return {"error": str(e)}
        
    finally:
        driver.quit()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
