# Prompt Engineering System: Text-to-SQL Pipeline

This document details the design and implementation of a two-stage Large Language Model (LLM) system that transforms generic user questions into executable SQL queries.

## 1. Context & Mock Database Setup
To allow the system to accurately map business questions to data, we define two hypothetical databases for a company named **TechCorp**:

1. **`hr_db`**: 
   * `employees` table: `id`, `name`, `department`, `salary`, `hire_date`
   * `performance` table: `employee_id`, `rating`, `review_date`
2. **`sales_db`**: 
   * `orders` table: `order_id`, `customer_id`, `amount`, `order_date`, `region`
   * `customers` table: `customer_id`, `company_name`, `industry`

---

## 2. Stage 1: Question Refinement (Prompt Design)

**Objective**: Take a vague, conversational question, identify the correct database, and rewrite it into a highly specific analytical question.

### The Prompt
```text
You are an expert Data Analyst at TechCorp. Your job is to take vague questions from business users and translate them into specific, analytical questions.

We have two databases available:
1. "hr_db" - Contains employee data, salaries, hiring, and performance reviews.
2. "sales_db" - Contains customer information, order history, revenue, and regional sales.

Instructions:
1. Read the user's generic question.
2. Identify which of the two databases is required to answer the question.
3. Rewrite the generic question into a highly specific question that a database engineer can easily write SQL for. Make reasonable assumptions to clarify vague terms (e.g., "doing well" usually means "highest revenue" or "highest performance rating").
4. Output your response STRICTLY as a JSON object with two keys: "refined_question" and "database_name". Do not output any other text or markdown formatting outside the JSON object.

Example Output:
{
  "refined_question": "What is the total sum of order amounts in the sales_db for the current year?",
  "database_name": "sales_db"
}

User Question: {user_input}
```

### Rationale & Iterations
* **Persona & Context**: Setting the "Data Analyst" persona primes the LLM for analytical thinking. Explicitly defining the available databases acts as a routing mechanism.
* **Assumption Handling**: Vague questions (e.g., "Who is doing well?") are problematic. The prompt explicitly instructs the LLM to make reasonable analytical assumptions (e.g., "doing well" = high revenue/ratings) to bridge the gap between conversational English and database logic.
* **Strict JSON Formatting**: A major challenge in Stage 1 is preventing the LLM from adding conversational fluff (e.g., "Here is the JSON you requested:"). The prompt uses capitalized constraints and an explicit example to enforce a clean JSON string output, which is necessary for the software to parse the results programmatically.

---

## 3. Stage 2: SQL Generation (Prompt Design)

**Objective**: Take the JSON output from Stage 1 and the target database schema, and generate a valid, executable SQL query.

### The Prompt
```text
You are an expert SQL Developer. Your task is to write a highly accurate SQL query based on a specific question and a provided database schema.

Here is the schema for the target database:
{database_schema}

Instructions:
1. Read the target question: {refined_question}
2. Write a single, valid PostgreSQL query that answers the question using ONLY the tables and columns provided in the schema above.
3. Use appropriate aggregations, joins, and filtering where necessary.
4. Output ONLY the raw SQL query. Do not wrap it in markdown code blocks (```sql) and do not provide any explanations.

Output format:
SELECT ...
```

### Rationale & Iterations
* **Dynamic Context Injection**: The placeholders `{database_schema}` and `{refined_question}` are injected programmatically by the system based on the output of Stage 1. This ensures the LLM isn't distracted by irrelevant schemas.
* **Preventing Hallucinations**: LLMs frequently guess column names (like `bonus_amount`) if they sound logical. The instruction to use "ONLY the tables and columns provided" heavily mitigates this hallucination.
* **Raw Output Formatting**: Just like Stage 1, we must strip away the LLM's conversational tendencies. Forbidding markdown code blocks ensures the output can be sent directly to the SQL execution engine without string parsing errors.

---

## 4. Pipeline Examples

Here is how the two-stage pipeline handles generic questions in practice:

### Example 1: The Vague Performance Question
* **Generic Question (User Input)**: "Who are our best people?"
* **Stage 1 JSON Output**:
  ```json
  {
    "refined_question": "Which employees have the highest performance rating in the most recent review period?",
    "database_name": "hr_db"
  }
  ```
* **Stage 2 SQL Output**:
  ```sql
  SELECT e.name, p.rating 
  FROM employees e 
  JOIN performance p ON e.id = p.employee_id 
  ORDER BY p.rating DESC 
  LIMIT 10;
  ```

### Example 2: The Vague Geographical Question
* **Generic Question (User Input)**: "How is California doing?"
* **Stage 1 JSON Output**:
  ```json
  {
    "refined_question": "What is the total order amount for all customers located in the California region?",
    "database_name": "sales_db"
  }
  ```
* **Stage 2 SQL Output**:
  ```sql
  SELECT sum(amount) as total_revenue 
  FROM orders 
  WHERE region = 'California';
  ```

### Example 3: Departmental Colloquialisms
* **Generic Question (User Input)**: "What do we pay the tech team?"
* **Stage 1 JSON Output**:
  ```json
  {
    "refined_question": "What is the average and total salary for all employees in the Technology department?",
    "database_name": "hr_db"
  }
  ```
* **Stage 2 SQL Output**:
  ```sql
  SELECT avg(salary) as average_salary, sum(salary) as total_salary 
  FROM employees 
  WHERE department = 'Technology';
  ```

---

## 5. System Effectiveness Analysis

### Strengths
* **Separation of Concerns**: By splitting the task into two stages (Routing/Refining -> Code Generation), the accuracy of the system increases drastically. Forcing an LLM to guess the context *and* write perfectly syntax-checked SQL in one single step overwhelms the model's attention, leading to errors.
* **Context Preservation**: Stage 1 creates a highly explicit bridge. By writing out the `refined_question`, the LLM effectively performs "Chain of Thought" reasoning before it is forced to write code in Stage 2.

### Challenges Encountered
1. **JSON Reliability**: Relying purely on prompt text to guarantee JSON output is sometimes brittle. Even with strict instructions, the model might occasionally output invalid JSON (e.g., trailing commas). *Future Solution*: Use API-level features like OpenAI's `response_format: { type: "json_object" }` or Function Calling.
2. **Extreme Ambiguity**: Highly ambiguous questions like "How are things?" provide too little context for Stage 1 to make an educated guess. The prompt forces an assumption, which might be wrong. *Future Solution*: Introduce a third stage or a fallback mechanism where the system returns a clarifying question to the user instead of guessing blindly.
3. **Complex Schema Handling**: As database schemas grow to hundreds of tables, injecting the entire schema into the Stage 2 prompt will exceed the context window. *Future Solution*: Implement a retrieval-augmented generation (RAG) system to only inject the schema of relevant tables based on semantic similarity to the `refined_question`.
