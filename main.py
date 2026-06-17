from fastapi import FastAPI
from openai import OpenAI
import json
from pydantic import BaseModel
import os




class PhotoRequest(BaseModel):
    image_base64: str
    user_prompt: str = ""

app = FastAPI()
@app.post("/analyze-meal-photo")
def analyze_meal_photo(request: PhotoRequest):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
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
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
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
def get_advice(
    calories: int, protein: int, carbs: int, fats: int, sugar: int, fiber: int,
    calories_goal: int, protein_goal: int, carbs_goal: int, fats_goal: int, sugar_goal: int, fiber_goal: int
):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""You are a personal diet coach. Today's stats (as % of goal):
            - Calories: {round(calories/calories_goal*100)}%
            - Protein: {round(protein/protein_goal*100)}%
            - Carbs: {round(carbs/carbs_goal*100)}%
            - Fats: {round(fats/fats_goal*100)}%
            - Sugar: {round(sugar/sugar_goal*100)}%
            - Fiber: {round(fiber/fiber_goal*100)}%

            Give ONE ultra-short advice (max 20 words). Priority rules:
            - Sugar over 100% is the most urgent issue — warn about it first
            - If protein and fiber are both low, mention whichever is lower
            - If calories are very low (under 30%) say to eat a bigger meal
            - If everything is in good range (70-100% for most, under 100% for sugar), give short praise
            - Pick only ONE most important issue, don't list multiple
            No numbers, no specific food suggestions, just the core action."""
        }]
    )
    return {"advice": response.choices[0].message.content}