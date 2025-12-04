# Full Production Translation Project (FastAPI MVC + Streamlit)
## Quickstart (Windows / VS Code)
1. Install Python 3.10
2. python -m venv venv
3. venv\Scripts\activate
4. pip install -r requirements.txt
5. Create a .env with OPENAI_API_KEY and MONGO_URI
6. Start MongoDB or use Atlas
7. Start backend: uvicorn backend.app.main:app --reload --port 8000
8. Start frontend: streamlit run frontend/streamlit_app.py
