# AML Report Automation

A comprehensive tool for AML (Anti-Money Laundering) report generation, featuring a FastAPI backend and a React-based frontend. This project automates the process of file upload, data verification, and report generation.

## Project Structure

- `backend/`: Python FastAPI REST API.
- `frontend/`: React + Vite frontend application.

---

## 🚀 Getting Started

### Prerequisites

- **Python**: 3.9+ 
- **Node.js**: 18.x or 20.x (LTS recommended)
- **NPM**: 9.x+

---

## 🛠 Backend Setup (Python)

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create a virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the API server**:
   ```bash
   python app.py
   ```
   The backend will start on `http://localhost:8000`.

---

## 💻 Frontend Setup (React)

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Run the development server**:
   ```bash
   npm run dev
   ```
   The frontend will be available at the URL provided in the terminal (usually `http://localhost:5173`).

---

## 📋 Features

- **Secure Login**: Simple authentication for report access.
- **Smart Upload**: Detects file types and extracts metadata (dates, columns).
- **Data Verification**: Automated reconciliation engine for integrity checks.
- **Report Generation**: Unified pipeline for generating Annex and Bank reports.
- **Audit Logging**: Comprehensive logging for all user actions.

## 📦 Requirements

### Backend dependencies:
- `fastapi`
- `uvicorn`
- `pandas`
- `openpyxl`
- `numpy`
- `python-multipart`

### Frontend dependencies:
- `react`
- `vite`
- `react-dom`

---

## 🤝 Contributing

1. Clone the repository:
   ```bash
   git clone https://github.com/sushantbhandari22/AML-Automation.git
   ```
2. Create your feature branch.
3. Commit your changes.
4. Push to the branch.
5. Open a Pull Request.
