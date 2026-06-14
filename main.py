from fastapi import FastAPI
from openai import OpenAI
import json
from pydantic import BaseModel
import os
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))



class PhotoRequest(BaseModel):
    image_base64: str
    user_prompt: str = ""

app = FastAPI()
@app.post("/analyze-meal-photo")
def analyze_meal_photo(request: PhotoRequest):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{request.image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": f"""Analyze this food image. {f'The user says: {request.user_prompt}.' if request.user_prompt else ''}
Use any objects visible (hands, plates, utensils) to estimate portion sizes accurately.
Estimate nutrition for total food visible. 
{'Also generate a short descriptive meal name (max 5 words).' if not request.user_prompt else ''}
Return ONLY a JSON object with these exact keys: calories, protein, carbs, fats, sugar, fiber, meal_name.
{'Set meal_name to: ' + request.user_prompt if request.user_prompt else ''}
All nutrition values must be plain integers. No markdown, no code blocks, just pure JSON. If no food visible, return exactly: nofood"""
        }]
        }]
    )
    
    raw = response.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if raw.lower() == "nofood":
        return {"error": "nofood"}
    return json.loads(raw) 



@app.get("/analyze-meal")

def analyze_meal(meal: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini", #   gpt-4o (strong model)   gpt-4o-mini (weak and cheap model)
        messages=[
            {
                "role": "user",
                "content": f"Analyze this food/meal: {meal}. Estimate the nutrition for a typical serving. Return ONLY a JSON object with these exact keys: calories, protein, carbs, fats, sugar, fiber. No markdown, no code blocks, just pure JSON. If the input is completely unrelated to food (like random words or code), return exactly: nofood"
            }
        ]
    )


    raw = response.choices[0].message.content
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    print(f"RAW RESPONSE: '{raw}'")  # add this

    if raw.lower() == "nofood":
        return {"error": "nofood"}
    print(json.loads(raw)["calories"])
    return json.loads(raw)



@app.get("/get-advice")
def get_advice(calories: int, protein: int, calories_goal: int, protein_goal: int):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""You are a personal diet coach. Today's stats:
            - Calories: {round(calories/calories_goal*100)}% of goal
            - Protein: {round(protein/protein_goal*100)}% of goal

            Give ONE ultra-short advice (max 20 words). Priority rules: (you don't have to tell the user about this, just find out a good breif insightful answer)
            - If calories % is lower than protein %: focus on calories
            - If protein % is lower than calories %: focus on protein  
            - If both under 30%: say to eat a big meal 
            - If both over 80%: give short praise
            - If anything over 100%: warn about it
            No numbers, no food suggestions, just the core action."""
        }]
    )
    return {"advice": response.choices[0].message.content}