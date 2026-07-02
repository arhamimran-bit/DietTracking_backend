from fastapi import FastAPI
from openai import OpenAI
import json
from pydantic import BaseModel
import os
import sqlite3
from datetime import date, timedelta





def init_db():
    conn = sqlite3.connect("/data/backend.db")     # usage limits 
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_limits (
            device_id TEXT PRIMARY KEY,
            date TEXT,
            prompt_count INTEGER,
            image_count INTEGER
        )
    """)
    conn.commit()
    conn.close()

    conn = sqlite3.connect("/data/backend.db")        #  mainly for pannel
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options_quantity INTEGER,
            options TEXT,
            is_active BOOLEAN,
            expires_at TEXT,
            created_at TEXT
        )
    """)
    try:
        conn.execute("ALTER TABLE feedback ADD COLUMN created_at TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()

    conn = sqlite3.connect("/data/backend.db")                #  feedback screen -> post responses
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback_from_post (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            option_selected TEXT,
            device_id TEXT
        )
    """)    
    conn.commit()
    conn.close()    

    conn = sqlite3.connect("/data/backend.db")                    #  feedback screen -> any specifc response
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback_specific (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            feedback TEXT 
        )
    """)    
    conn.commit()
    conn.close()    
init_db()


def get_counts(device_id: str):
    conn = sqlite3.connect("/data/backend.db")
    row = conn.execute(
        "SELECT date, prompt_count, image_count FROM usage_limits WHERE device_id = ?",
        (device_id,)
    ).fetchone()

    today = str(date.today())

    if row is None:
        
        # No record exists yet for this device — create one
        conn.execute(
            "INSERT INTO usage_limits (device_id, date, prompt_count, image_count) VALUES (?, ?, 0, 0)",
            (device_id, today)
        )
        conn.commit()
        conn.close()
        return 0, 0
     

    stored_date, prompt_count, image_count = row

    # YOUR TURN: write the condition here.
    if stored_date != today:
        conn.execute(
            "UPDATE usage_limits SET date = ?, prompt_count = 0, image_count = 0 WHERE device_id = ?",
            (today, device_id)
        )
        conn.commit()
        conn.close()
        return 0, 0
    else:
        conn.close()
        return prompt_count, image_count



class PhotoRequest(BaseModel):
    image_base64: str
    user_prompt: str = ""
    device_id: str


class PanelRequest(BaseModel):
    question: str
    options: list[str]
    active: bool
    duration_days: int

class TextFeedbackRequest(BaseModel):
    feedback: str
    device_id: str


class ToggleActiveRequest(BaseModel):
    is_active: bool

app = FastAPI()
@app.patch("/panel_posts/{post_id}")
def toggle_post_active(post_id: int, request: ToggleActiveRequest):
    conn = sqlite3.connect("/data/backend.db")
    conn.execute("UPDATE feedback SET is_active = ? WHERE id = ?", (request.is_active, post_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/panel_posts/{post_id}")
def delete_post(post_id: int):
    conn = sqlite3.connect("/data/backend.db")
    conn.execute("DELETE FROM feedback WHERE id = ?", (post_id,))
    conn.execute("DELETE FROM feedback_from_post WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/submit_text_feedback")
def submit_text_feedback(request: TextFeedbackRequest):
    conn = sqlite3.connect("/data/backend.db")
    conn.execute(
        "INSERT INTO feedback_specific (user_id, feedback) VALUES (?, ?)",
        (request.device_id, request.feedback)
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/panel_posts")
def panel_posts():
    today = str(date.today())
    conn = sqlite3.connect("/data/backend.db")
    conn.execute(
        "UPDATE feedback SET is_active = 0 WHERE expires_at < ? AND is_active = 1",
        (today,)
    )
    conn.commit()
    rows = conn.execute("SELECT id, question, options, is_active, expires_at, created_at FROM feedback").fetchall()
    conn.close()
    posts = []
    for r in rows:
        posts.append({
            "id": r[0], "question": r[1],
            "options": r[2].split(","),
            "is_active": bool(r[3]), "expires_at": r[4], "created_at": r[5]
        })
    return {"posts": posts}


@app.get("/text_feedback")
def get_text_feedback():
    conn = sqlite3.connect("/data/backend.db")
    rows = conn.execute("SELECT id, user_id, feedback FROM feedback_specific").fetchall()
    conn.close()

    feedback_list = [{"id": r[0], "device_id": r[1], "feedback": r[2]} for r in rows]
    return {"feedback": feedback_list}


@app.delete("/text_feedback")
def clear_text_feedback():
    conn = sqlite3.connect("/data/backend.db")
    conn.execute("DELETE FROM feedback_specific")
    conn.commit()
    conn.close()
    return {"status": "ok"}



@app.post("/panel_new_post")
def panel_new_post(request: PanelRequest):

    options_str = ",".join(request.options)
    expires = str(date.today() + timedelta(days=request.duration_days))

    conn = sqlite3.connect("/data/backend.db")
    conn.execute(
        "INSERT INTO feedback (question, options_quantity, options, is_active, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (request.question, len(request.options), options_str, request.active, expires, str(date.today()))
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}    

class ResponseRequest(BaseModel):
    post_id: int
    option_selected: str
    device_id: str

@app.post("/submit_response")
def submit_response(request: ResponseRequest):
    conn = sqlite3.connect("/data/backend.db")
    conn.execute(
        "INSERT INTO feedback_from_post (post_id, option_selected, device_id) VALUES (?, ?, ?)",
        (request.post_id, request.option_selected, request.device_id)
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/posts/{post_id}/results")
def get_post_results(post_id: int):
    conn = sqlite3.connect("/data/backend.db")
    rows = conn.execute(
        "SELECT option_selected, COUNT(*) FROM feedback_from_post WHERE post_id = ? GROUP BY option_selected",
        (post_id,)
    ).fetchall()
    conn.close()

    total = sum(row[1] for row in rows)
    results = []
    for option, count in rows:
        pct = round((count / total) * 100, 1) if total > 0 else 0
        results.append({"option": option, "count": count, "percentage": pct})

    return {"post_id": post_id, "total_responses": total, "results": results}


@app.get("/posts/active")
def get_active_posts(device_id: str):
    today = str(date.today())
    conn = sqlite3.connect("/data/backend.db")

    conn.execute(
        "UPDATE feedback SET is_active = 0 WHERE expires_at < ? AND is_active = 1",
        (today,)
    )
    conn.commit()

    rows = conn.execute("""
        SELECT id, question, options FROM feedback
        WHERE is_active = 1
        AND id NOT IN (
            SELECT post_id FROM feedback_from_post WHERE device_id = ?
        )
    """, (device_id,)).fetchall()
    conn.close()

    posts = []
    for row in rows:
        posts.append({
            "id": row[0],
            "question": row[1],
            "options": row[2].split(",")
        })
    return {"posts": posts}


def increment_count(device_id: str, is_photo: bool):
    conn = sqlite3.connect("/data/backend.db")
    
    if is_photo:
        conn.execute(
            "UPDATE usage_limits SET image_count = image_count + 1 WHERE device_id = ?",
            (device_id,)
        )
    else:
        conn.execute(
            "UPDATE usage_limits SET prompt_count = prompt_count + 1 WHERE device_id = ?",
            (device_id,)
        ) 

    conn.commit()
    conn.close()



@app.post("/analyze-meal-photo")
def analyze_meal_photo(request: PhotoRequest):

    prompt_count, image_count = get_counts(request.device_id)

    if image_count < 4: 

        increment_count(request.device_id, is_photo=True)

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o", #ai model 
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
    Estimate nutrition for total food visible. For sugar specifically: most whole foods (meat, rice, bread, vegetables, plain dairy) contain very little or no sugar — estimate sugar conservatively and only assign high sugar values to foods that are overtly sweet (desserts, candy, soda, fruit, sweetened sauces). Sugar should almost always be a small fraction of total carbs, not a large one, unless the food is clearly a sweet/sugary item. 
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
    else:
        return {"error": "Picture limit reached"}




@app.get("/analyze-meal")

def analyze_meal(meal: str, device_id: str):

    if meal.strip() == "":
        return {"error": "nofood"}

    prompt_count, image_count = get_counts(device_id)
    if prompt_count < 10 :
        
        increment_count(device_id, is_photo=False)
    
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini", # ai model                  gpt-4o (strong model)   gpt-4o-mini (weak and cheap model)
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this food/meal: {meal}. Estimate the nutrition for a typical serving. Return ONLY a JSON object with these exact keys: calories, protein, carbs, fats, sugar, fiber. No markdown, no code blocks, just pure JSON. For sugar specifically: most whole foods (meat, rice, bread, vegetables, plain dairy) contain very little or no sugar — estimate sugar conservatively and only assign high sugar values to foods that are overtly sweet (desserts, candy, soda, fruit, sweetened sauces). Sugar should almost always be a small fraction of total carbs, not a large one, unless the food is clearly a sweet/sugary item. If the input is completely unrelated to food (like random words or code), return exactly: nofood"                }
            ]
        )


        raw = response.choices[0].message.content
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        print(f"RAW RESPONSE: '{raw}'")  # add this

        if raw.lower() == "nofood":
            return {"error": "nofood"}
        
        print(json.loads(raw)["calories"])
        return json.loads(raw)
    else: 
        return {"error" : "Prompt limit reached"}



@app.get("/get-advice")        
def get_advice(
    calories: int, protein: int, carbs: int, fats: int, sugar: int, fiber: int,
    calories_goal: int, protein_goal: int, carbs_goal: int, fats_goal: int, sugar_goal: int, fiber_goal: int
):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini", #ai model
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