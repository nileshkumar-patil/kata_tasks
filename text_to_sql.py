import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key or api_key == "your_api_key_here":
    print("ERROR: Please set a valid GEMINI_API_KEY in your .env file.")
    exit(1)

genai.configure(api_key=api_key)

# We use Gemini 1.5 Flash for speed and cost-effectiveness
model = genai.GenerativeModel('gemini-1.5-flash')

# 1. Mock Database Schemas
schemas = {
    "hr_db": """
Table: employees
Columns: id (INT), name (VARCHAR), department (VARCHAR), salary (INT), hire_date (DATE)

Table: performance
Columns: employee_id (INT), rating (INT), review_date (DATE)
""",
    "sales_db": """
Table: orders
Columns: order_id (INT), customer_id (INT), amount (DECIMAL), order_date (DATE), region (VARCHAR)

Table: customers
Columns: customer_id (INT), company_name (VARCHAR), industry (VARCHAR)
"""
}

def refine_question(user_input: str) -> dict:
    """Stage 1: Question Refinement and Database Routing"""
    prompt = f"""
You are an expert Data Analyst at TechCorp. Your job is to take vague questions from business users and translate them into specific, analytical questions.

We have two databases available:
1. "hr_db" - Contains employee data, salaries, hiring, and performance reviews.
2. "sales_db" - Contains customer information, order history, revenue, and regional sales.

Instructions:
1. Read the user's generic question.
2. Identify which of the two databases is required to answer the question.
3. Rewrite the generic question into a highly specific question that a database engineer can easily write SQL for. Make reasonable assumptions to clarify vague terms.
4. Output your response STRICTLY as a JSON object with two keys: "refined_question" and "database_name".

User Question: {user_input}
"""
    # Force the model to return JSON
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)

def generate_sql(refined_question: str, database_name: str) -> str:
    """Stage 2: SQL Generation based on the chosen schema"""
    schema = schemas.get(database_name)
    if not schema:
        return f"Error: Database '{database_name}' not found."

    prompt = f"""
You are an expert SQL Developer. Your task is to write a highly accurate SQL query based on a specific question and a provided database schema.

Here is the schema for the target database:
{schema}

Instructions:
1. Read the target question: {refined_question}
2. Write a single, valid PostgreSQL query that answers the question using ONLY the tables and columns provided in the schema above.
3. Use appropriate aggregations, joins, and filtering where necessary.
4. Output ONLY the raw SQL query. Do not wrap it in markdown code blocks (```sql) and do not provide any explanations.

Output format:
SELECT ...
"""
    response = model.generate_content(prompt)
    
    # Clean up any potential markdown if the model disobeys instructions
    sql = response.text.strip()
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.endswith("```"):
        sql = sql[:-3]
        
    return sql.strip()

if __name__ == "__main__":
    print("=== Text-to-SQL Pipeline Started ===\n")
    
    test_questions = [
        "Who are our best people?",
        "How is California doing?",
        "What do we pay the tech team?"
    ]
    
    for q in test_questions:
        print(f"User Question: '{q}'")
        
        # Stage 1
        print("Running Stage 1 (Refinement)...")
        stage1_result = refine_question(q)
        print(f"  Refined Question: {stage1_result.get('refined_question')}")
        print(f"  Target Database:  {stage1_result.get('database_name')}")
        
        # Stage 2
        print("Running Stage 2 (SQL Generation)...")
        sql_query = generate_sql(stage1_result.get('refined_question'), stage1_result.get('database_name'))
        print("  Generated SQL:")
        print(f"    {sql_query}")
        print("-" * 50)
