@echo off
echo Starting AgroConnect...

IF NOT EXIST "backend\venv\Scripts\activate.bat" (
    echo Creating virtual environment in backend\venv...
    python -m venv backend\venv
)

echo Activating virtual environment...
call backend\venv\Scripts\activate.bat

echo Installing/updating dependencies...
pip install -r requirements.txt

echo Starting Flask server...
cd backend
echo ==========================================
echo  The server will be running at:
echo  http://127.0.0.1:5000
echo ==========================================
python app.py
