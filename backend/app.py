from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from flask_bcrypt import Bcrypt
import os
import joblib
import numpy as np
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

# Initialize extensions and models
from models import (
    db, User, 
    CropRecommendation, SoilHealthRecord, 
    YieldPrediction, IrrigationPlan, FieldSoilMetric
)

login_manager = LoginManager()
bcrypt = Bcrypt()

# --- LOAD TRAINED ML MODEL ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(CURRENT_DIR, 'crop_model.joblib')
ml_model_payload = None

try:
    if os.path.exists(MODEL_PATH):
        ml_model_payload = joblib.load(MODEL_PATH)
        print(f"[AgroConnect ML] Successfully loaded Crop Recommendation Model from {MODEL_PATH}")
    else:
        print("[AgroConnect ML] crop_model.joblib not found. Run train_model.py to generate it.")
except Exception as e:
    print(f"[AgroConnect ML] Warning loading model: {e}")

# Agronomic knowledge dictionary for model predictions
CROP_AGRONOMIC_INFO = {
    'rice': {'sowing': 'June to July (Kharif)', 'reason': 'High humidity, submerged soil tolerance, and prolonged warm temperatures favor robust paddy growth.'},
    'maize': {'sowing': 'June to July / October (Rabi)', 'reason': 'Moderate rainfall with well-drained loamy soil provides optimal cob yield.'},
    'chickpea': {'sowing': 'October to November (Rabi)', 'reason': 'Cool climate, low humidity, and residual soil moisture encourage nodulation.'},
    'kidneybeans': {'sowing': 'October to November (Rabi)', 'reason': 'Moderate temperatures and nitrogen-balanced fertile soil prevent blossom drop.'},
    'pigeonpeas': {'sowing': 'June to July (Kharif)', 'reason': 'Deep root penetration tolerates drought and thrives under monsoon precipitation.'},
    'mothbeans': {'sowing': 'July to August (Kharif)', 'reason': 'Exceptionally drought-hardy legume ideal for arid sandy-loam conditions.'},
    'mungbean': {'sowing': 'March to April (Zaid) / July', 'reason': 'Short lifecycle with warm temperatures and light rains maximizes pod setting.'},
    'blackgram': {'sowing': 'June to July / February (Zaid)', 'reason': 'Thrives in warm, humid weather with well-drained alluvial or black soils.'},
    'lentil': {'sowing': 'October to December (Rabi)', 'reason': 'Cold-tolerant pulse crop that utilizes cool winter conditions with low moisture.'},
    'pomegranate': {'sowing': 'July to August / February', 'reason': 'Arid to semi-arid tropical climate with warm dry summers and good drainage.'},
    'banana': {'sowing': 'June to August / February to March', 'reason': 'High potassium, organic rich soil, and consistent warmth sustain rapid pseudostem development.'},
    'mango': {'sowing': 'July to August (Monsoon)', 'reason': 'Deep alluvial soil with distinct dry season triggers synchronous blooming.'},
    'grapes': {'sowing': 'October to November', 'reason': 'High potassium and phosphorus with dry sunny ripening season maximize sugar content.'},
    'watermelon': {'sowing': 'February to March (Zaid)', 'reason': 'High temperatures and warm sandy loam soil yield sweet, well-sized melons.'},
    'muskmelon': {'sowing': 'February to March (Zaid)', 'reason': 'Warm, dry sunny weather during fruiting produces superior aromatic sweetness.'},
    'apple': {'sowing': 'December to March', 'reason': 'Temperate climate with adequate winter chilling hours and well-drained loams.'},
    'orange': {'sowing': 'July to August / January to February', 'reason': 'Subtropical conditions with well-aerated soil and moderate humidity ensure juiciness.'},
    'papaya': {'sowing': 'June to September / February', 'reason': 'Tropical warmth, high solar radiation, and porous soil promote continuous fruit bearing.'},
    'coconut': {'sowing': 'May to June (Monsoon)', 'reason': 'High coastal humidity, consistent year-round warmth, and sandy-loam soil profiles.'},
    'cotton': {'sowing': 'April to May / June', 'reason': 'Warm sunny days, deep moisture-retentive black soil, and moderate rainfall during vegetative growth.'},
    'jute': {'sowing': 'March to May', 'reason': 'Warm, humid climate with abundant rainfall and alluvial riverbed silt.'},
    'coffee': {'sowing': 'June to December', 'reason': 'High altitude shaded topography, rich organic humus, and humid tropical temperatures.'}
}


import pandas as pd

def predict_crop_ml(n, p, k, temp, hum, ph, rain):
    """Predict crop and return recommendation, confidence, and agronomic reasoning."""
    if ml_model_payload and 'model' in ml_model_payload:
        try:
            model = ml_model_payload['model']
            features = pd.DataFrame(
                [[float(n), float(p), float(k), float(temp), float(hum), float(ph), float(rain)]],
                columns=['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
            )
            pred_class = model.predict(features)[0]
            
            # Confidence score
            proba = model.predict_proba(features)[0]
            max_proba = float(np.max(proba))
            conf_percent = f"{max_proba * 100:.1f}%"
            
            crop_name = pred_class.capitalize()
            crop_key = pred_class.lower()
            info = CROP_AGRONOMIC_INFO.get(crop_key, {
                'sowing': 'Seasonal standard',
                'reason': 'Optimal nutrient balance and environmental conditions align with this crop.'
            })
            
            return {
                'crop': crop_name,
                'confidence': conf_percent,
                'sowing_time': info['sowing'],
                'reason': info['reason']
            }
        except Exception as e:
            print(f"[AgroConnect ML] Prediction failed: {e}")
            
    # Fallback heuristic if ML model is unavailable
    if float(rain) > 180 and float(hum) > 75:
        return {'crop': 'Rice', 'confidence': '91.2%', 'sowing_time': 'June to July', 'reason': 'High rainfall and humidity indicate ideal conditions for Rice.'}
    elif float(temp) < 22 and float(rain) < 100:
        return {'crop': 'Chickpea', 'confidence': '89.5%', 'sowing_time': 'October to November', 'reason': 'Cool climate and low rainfall match Chickpea requirements.'}
    elif float(temp) > 28 and float(rain) < 70:
        return {'crop': 'Watermelon', 'confidence': '88.0%', 'sowing_time': 'February to March', 'reason': 'Warm dry season favors Watermelon.'}
    else:
        return {'crop': 'Maize', 'confidence': '87.4%', 'sowing_time': 'June to July', 'reason': 'Balanced NPK and temperature levels suit Maize growth.'}


def seed_user_reports(user_id, farm_size=5.0):
    """Seed a specific user with rich dummy reports across all tables."""
    now = datetime.utcnow()
    # 1. Crop Recommendations
    c1 = CropRecommendation(
        user_id=user_id,
        nitrogen=78.5, phosphorus=42.0, potassium=39.0,
        temperature=26.5, humidity=82.0, ph=6.4, rainfall=235.0,
        season='Kharif (Monsoon)', soil_type='Clay Loam',
        recommended_crop='Rice', confidence='98.7%',
        reason='High humidity, heavy seasonal precipitation, and optimal nitrogen profile maximize tillering in Rice.',
        sowing_time='June to July (Monsoon)',
        created_at=now - timedelta(days=22)
    )
    c2 = CropRecommendation(
        user_id=user_id,
        nitrogen=120.0, phosphorus=52.0, potassium=24.0,
        temperature=27.2, humidity=75.0, ph=6.8, rainfall=82.0,
        season='Kharif (Monsoon)', soil_type='Black Soil',
        recommended_crop='Cotton', confidence='96.4%',
        reason='High soil moisture retention capacity and optimal thermal units accelerate boll development.',
        sowing_time='April to May',
        created_at=now - timedelta(days=15)
    )
    c3 = CropRecommendation(
        user_id=user_id,
        nitrogen=35.0, phosphorus=78.0, potassium=72.0,
        temperature=17.5, humidity=20.0, ph=7.2, rainfall=62.0,
        season='Rabi (Winter)', soil_type='Loamy',
        recommended_crop='Chickpea', confidence='97.8%',
        reason='Cool temperatures and dry atmospheric conditions prevent pod rot and boost nodulation.',
        sowing_time='October to November',
        created_at=now - timedelta(days=8)
    )
    c4 = CropRecommendation(
        user_id=user_id,
        nitrogen=105.0, phosphorus=88.0, potassium=52.0,
        temperature=28.0, humidity=80.0, ph=6.5, rainfall=125.0,
        season='Kharif (Monsoon)', soil_type='Alluvial',
        recommended_crop='Banana', confidence='95.2%',
        reason='Abundant potassium and balanced moisture supply favor pseudostem thickness and bunch size.',
        sowing_time='July to August',
        created_at=now - timedelta(days=2)
    )
    db.session.add_all([c1, c2, c3, c4])

    # 2. Soil Health Records
    s1 = SoilHealthRecord(
        user_id=user_id,
        ph=6.7, nitrogen=115.0, phosphorus=48.0, potassium=42.0, organic_carbon=0.68,
        status='Optimal & Healthy',
        fertilizer_recommendation='Apply standard NPK (120:60:40) with 2 tons of well-decomposed FYM (Farm Yard Manure).',
        created_at=now - timedelta(days=25)
    )
    s2 = SoilHealthRecord(
        user_id=user_id,
        ph=5.6, nitrogen=65.0, phosphorus=28.0, potassium=30.0, organic_carbon=0.45,
        status='Acidic (Requires Lime)',
        fertilizer_recommendation='Broadcast agricultural dolomite lime at 2.2 tons/acre 3 weeks prior to sowing.',
        created_at=now - timedelta(days=12)
    )
    s3 = SoilHealthRecord(
        user_id=user_id,
        ph=7.8, nitrogen=90.0, phosphorus=38.0, potassium=45.0, organic_carbon=0.58,
        status='Slightly Alkaline (Requires Gypsum)',
        fertilizer_recommendation='Apply elemental sulfur (25 kg/acre) and agricultural gypsum to reduce pH to neutral range.',
        created_at=now - timedelta(days=3)
    )
    db.session.add_all([s1, s2, s3])

    # 3. Yield Predictions
    y1 = YieldPrediction(
        user_id=user_id,
        crop='Rice', farm_size=farm_size or 5.0, season='Kharif',
        total_yield=187.0, profit=467500.0,
        duration_days='120 Days', quality_grade='Grade A (Export Quality)',
        created_at=now - timedelta(days=28)
    )
    y2 = YieldPrediction(
        user_id=user_id,
        crop='Cotton', farm_size=farm_size or 5.0, season='Kharif',
        total_yield=110.5, profit=331500.0,
        duration_days='160 Days', quality_grade='Grade A+ (Premium)',
        created_at=now - timedelta(days=18)
    )
    y3 = YieldPrediction(
        user_id=user_id,
        crop='Maize', farm_size=farm_size or 5.0, season='Rabi',
        total_yield=153.0, profit=306000.0,
        duration_days='105 Days', quality_grade='Grade B (Standard Commercial)',
        created_at=now - timedelta(days=7)
    )
    y4 = YieldPrediction(
        user_id=user_id,
        crop='Wheat', farm_size=farm_size or 5.0, season='Rabi',
        total_yield=170.0, profit=391000.0,
        duration_days='135 Days', quality_grade='Grade A (Premium Milling)',
        created_at=now - timedelta(days=1)
    )
    db.session.add_all([y1, y2, y3, y4])

    # 4. Irrigation Plans
    i1 = IrrigationPlan(
        user_id=user_id,
        farm_size=farm_size or 5.0,
        soil_type='Clay Loam', water_source='Canal',
        temperature=31.5, rain_chance=20.0, wind_speed=14.0,
        frequency='Every 3 Days',
        warning='Root-zone water levels are stable. Maintain furrow irrigation cycles.',
        water_need='Moderate',
        created_at=now - timedelta(days=20)
    )
    i2 = IrrigationPlan(
        user_id=user_id,
        farm_size=farm_size or 5.0,
        soil_type='Sandy Loam', water_source='Drip System',
        temperature=35.0, rain_chance=5.0, wind_speed=22.0,
        frequency='Daily (Micro-dosing)',
        warning='High atmospheric vapor deficit detected. Operate drip emitters in split morning-evening cycles.',
        water_need='High',
        created_at=now - timedelta(days=5)
    )
    db.session.add_all([i1, i2])

    # 5. Field Soil Metrics
    f1 = FieldSoilMetric(
        user_id=user_id,
        farm_size=farm_size or 5.0,
        soil_type='black', water_source='canal',
        recommended_crop='Cotton', seed_bags=17, water_need='Medium',
        created_at=now - timedelta(days=26)
    )
    f2 = FieldSoilMetric(
        user_id=user_id,
        farm_size=farm_size or 5.0,
        soil_type='alluvial', water_source='tubewell',
        recommended_crop='Rice', seed_bags=26, water_need='High',
        created_at=now - timedelta(days=14)
    )
    f3 = FieldSoilMetric(
        user_id=user_id,
        farm_size=farm_size or 5.0,
        soil_type='red', water_source='rain',
        recommended_crop='Chickpea / Pulses', seed_bags=12, water_need='Low',
        created_at=now - timedelta(days=4)
    )
    db.session.add_all([f1, f2, f3])
    db.session.commit()


def seed_dummy_database(app_instance):
    """Seed the database with a demo farmer and realistic reports across all relational tables."""
    with app_instance.app_context():
        # Ensure tables exist
        db.create_all()
        
        # Check or create default user
        demo_user = User.query.filter_by(mobile_number='9876543210').first()
        if not demo_user:
            demo_user = User(
                farmer_name='Ramesh Patel',
                mobile_number='9876543210',
                password_hash=bcrypt.generate_password_hash('Farmer@123').decode('utf-8'),
                village='Khed Shivapur',
                district='Pune',
                farm_name='Patel Green Farms',
                farm_size=8.5,
                primary_crop='Rice'
            )
            db.session.add(demo_user)
            db.session.commit()
            print("[AgroConnect Seed] Created default demo user: Ramesh Patel (9876543210 / Farmer@123)")

        # Seed reports for all existing users who lack yield predictions
        all_users = User.query.all()
        for u in all_users:
            has_yield = YieldPrediction.query.filter_by(user_id=u.id).first()
            if not has_yield:
                print(f"[AgroConnect Seed] Seeding reports for user ID {u.id} ({u.farmer_name})...")
                seed_user_reports(u.id, u.farm_size)


def create_app():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, 'frontend', 'templates')
    static_dir = os.path.join(base_dir, 'frontend', 'static')
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir,
                static_url_path='/static')
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    
    default_db_url = 'postgresql+psycopg2://postgres:Dev26%402006@localhost:5432/agroconnect'
    db_uri = os.environ.get('DATABASE_URL', default_db_url)
    if db_uri.startswith('postgresql'):
        try:
            from sqlalchemy import create_engine, text
            probe_engine = create_engine(db_uri, connect_args={'connect_timeout': 3})
            with probe_engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            probe_engine.dispose()
        except Exception as e:
            print(f"[AgroConnect] PostgreSQL connection failed: {e}")
            print("[AgroConnect] Falling back to SQLite database (sqlite:///agroconnect.db)...")
            db_uri = 'sqlite:///agroconnect.db'
            
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    
    login_manager.login_view = 'login_page'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
        
    # --- TEMPLATE ROUTES ---
    @app.route('/')
    def index():
        return render_template('index.html')
        
    @app.route('/login')
    def login_page():
        return render_template('login.html')
        
    @app.route('/register')
    def register_page():
        return render_template('register.html')
        
    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')
        
    @app.route('/soil-health')
    @login_required
    def soil_health():
        return render_template('soil-health.html')
        
    @app.route('/crop-rec')
    @login_required
    def crop_rec():
        return render_template('crop-rec.html')
        
    @app.route('/yield-prediction')
    @login_required
    def yield_prediction():
        return render_template('yield-prediction.html')
        
    @app.route('/irrigation')
    @login_required
    def irrigation():
        return render_template('irrigation.html')
        
    @app.route('/weather')
    @login_required
    def weather():
        return render_template('weather.html')
        
    @app.route('/farm-reports')
    @login_required
    def farm_reports():
        return render_template('farm-reports.html')
        
    @app.route('/analytics')
    @login_required
    def analytics():
        return render_template('analytics.html')

    # --- API ROUTES ---
    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.get_json() or {}
        
        # Check if mobile already exists
        existing_user = User.query.filter_by(mobile_number=data.get('mobile')).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'Mobile number already registered.'}), 400
            
        hashed_password = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
        
        new_user = User(
            farmer_name=data.get('name'),
            mobile_number=data.get('mobile'),
            password_hash=hashed_password,
            village=data.get('village', ''),
            district=data.get('district', ''),
            farm_name=data.get('farm', ''),
            farm_size=float(data.get('acres', 0)) if data.get('acres') else None,
            primary_crop=data.get('crop', '')
        )
        
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Registration successful!'})

    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        user = User.query.filter_by(mobile_number=data.get('mobile')).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, data.get('password')):
            login_user(user)
            user_data = {
                'name': user.farmer_name,
                'mobile': user.mobile_number,
                'farm': user.farm_name,
                'size': user.farm_size,
                'crop': user.primary_crop
            }
            return jsonify({'success': True, 'message': 'Login successful!', 'user': user_data})
        else:
            return jsonify({'success': False, 'message': 'Invalid mobile number or password.'}), 401

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('index'))
        
    @app.route('/api/user/profile', methods=['GET'])
    @login_required
    def get_profile():
        user_data = {
            'name': current_user.farmer_name or 'Farmer',
            'mobile': current_user.mobile_number,
            'farm': current_user.farm_name or 'Farm',
            'size': current_user.farm_size or 0,
            'crop': current_user.primary_crop or '-',
            'village': current_user.village or '-',
            'district': current_user.district
        }
        return jsonify({'success': True, 'user': user_data})
        
    @app.route('/api/user/profile/update', methods=['POST'])
    @login_required
    def update_profile():
        data = request.get_json() or {}
        current_user.farmer_name = data.get('name', current_user.farmer_name)
        current_user.farm_name = data.get('farm', current_user.farm_name)
        current_user.village = data.get('village', current_user.village)
        try:
            current_user.farm_size = float(data.get('size'))
        except (ValueError, TypeError):
            pass
        current_user.primary_crop = data.get('crop', current_user.primary_crop)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Profile updated successfully'})

    # --- MACHINE LEARNING CROP RECOMMENDATION ENDPOINT ---
    @app.route('/api/crop-rec/predict', methods=['POST'])
    @login_required
    def crop_rec_predict():
        data = request.get_json() or {}
        try:
            n = float(data.get('n', data.get('nitrogen', 80.0)))
            p = float(data.get('p', data.get('phosphorus', 45.0)))
            k = float(data.get('k', data.get('potassium', 40.0)))
            temp = float(data.get('temperature', data.get('temp', 26.0)))
            hum = float(data.get('humidity', data.get('hum', 75.0)))
            ph = float(data.get('ph', 6.5))
            rain = float(data.get('rainfall', data.get('rain', 150.0)))
            season = data.get('season', 'Kharif')
            soil = data.get('soil', data.get('soil_type', 'Loamy'))
            
            result = predict_crop_ml(n, p, k, temp, hum, ph, rain)
            
            # Save recommendation directly into the relational CropRecommendation table
            rec = CropRecommendation(
                user_id=current_user.id,
                nitrogen=n,
                phosphorus=p,
                potassium=k,
                temperature=temp,
                humidity=hum,
                ph=ph,
                rainfall=rain,
                season=season,
                soil_type=soil,
                recommended_crop=result['crop'],
                confidence=result['confidence'],
                reason=result['reason'],
                sowing_time=result['sowing_time']
            )
            db.session.add(rec)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'recommended_crop': result['crop'],
                'confidence': result['confidence'],
                'sowing_time': result['sowing_time'],
                'reason': result['reason']
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

    # --- LIVE WEATHER API ENDPOINT ---
    WMO_WEATHER_CODES = {
        0: ('Clear Sky', '☀️'),
        1: ('Mainly Clear', '🌤️'),
        2: ('Partly Cloudy', '⛅'),
        3: ('Overcast', '☁️'),
        45: ('Foggy', '🌫️'),
        48: ('Depositing Rime Fog', '🌫️'),
        51: ('Light Drizzle', '🌦️'),
        53: ('Moderate Drizzle', '🌦️'),
        55: ('Dense Drizzle', '🌧️'),
        61: ('Slight Rain', '🌦️'),
        63: ('Moderate Rain', '🌧️'),
        65: ('Heavy Rain', '🌧️'),
        71: ('Slight Snow', '🌨️'),
        73: ('Moderate Snow', '🌨️'),
        75: ('Heavy Snow', '🌨️'),
        80: ('Slight Showers', '🌦️'),
        81: ('Moderate Showers', '🌧️'),
        82: ('Violent Showers', '⛈️'),
        95: ('Thunderstorm', '⛈️'),
        96: ('Thunderstorm with Hail', '⛈️')
    }

    def fetch_live_weather(lat, lon, location_name="Local Farm"):
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m"
                f"&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,precipitation_sum,precipitation_probability_max"
                f"&timezone=auto&forecast_days=7"
            )
            req = urllib.request.Request(url, headers={'User-Agent': 'AgroConnect/1.0'})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                
            cur = data.get('current', {})
            daily = data.get('daily', {})
            
            w_code = cur.get('weather_code', 0)
            cond_text, cond_icon = WMO_WEATHER_CODES.get(w_code, ('Clear Sky', '☀️'))
            
            temp = cur.get('temperature_2m', 28.0)
            humidity = cur.get('relative_humidity_2m', 60.0)
            wind_speed = cur.get('wind_speed_10m', 10.0)
            rain_mm = cur.get('precipitation', 0.0)
            uv_max = (daily.get('uv_index_max') or [6.0])[0] if daily.get('uv_index_max') else 6.0
            
            # Advisory generation
            precip_sum_today = (daily.get('precipitation_sum') or [0])[0] or 0.0
            if rain_mm > 5.0 or precip_sum_today > 10.0:
                irrigation_adv = "Heavy rainfall detected/forecast today. Postpone irrigation to prevent waterlogging."
                spraying_adv = "Rainfall hazard: Delay pesticide and foliar fertilizer application."
            elif humidity < 40 and temp > 32:
                irrigation_adv = "High evapotranspiration rate. Deep irrigation recommended during early morning."
                spraying_adv = "Spraying optimal in early morning before midday heat spikes."
            else:
                irrigation_adv = "Soil moisture balance is optimal. Proceed with standard scheduled irrigation."
                spraying_adv = "Favorable conditions for foliar nutrient and pest management spraying."
                
            if wind_speed > 18:
                spraying_adv = f"Strong winds ({wind_speed} km/h). Delay spraying to avoid chemical spray drift."

            forecast_days = []
            dates = daily.get('time', [])
            max_temps = daily.get('temperature_2m_max', [])
            min_temps = daily.get('temperature_2m_min', [])
            w_codes = daily.get('weather_code', [])
            precip_probs = daily.get('precipitation_probability_max', [])
            
            for i in range(min(len(dates), 7)):
                d_code = w_codes[i] if i < len(w_codes) else 0
                d_cond, d_icon = WMO_WEATHER_CODES.get(d_code, ('Clear', '☀️'))
                try:
                    dt = datetime.strptime(dates[i], '%Y-%m-%d')
                    day_name = dt.strftime('%a')
                except Exception:
                    day_name = f"Day {i+1}"
                
                forecast_days.append({
                    'date': dates[i],
                    'day': day_name,
                    'temp_max': max_temps[i] if i < len(max_temps) else temp,
                    'temp_min': min_temps[i] if i < len(min_temps) else temp - 5,
                    'condition': d_cond,
                    'icon': d_icon,
                    'rain_prob': precip_probs[i] if i < len(precip_probs) else 0
                })
                
            return {
                'success': True,
                'location': {
                    'name': location_name,
                    'latitude': lat,
                    'longitude': lon
                },
                'current': {
                    'temperature': temp,
                    'feels_like': cur.get('apparent_temperature', temp),
                    'humidity': humidity,
                    'wind_speed': wind_speed,
                    'wind_direction': cur.get('wind_direction_10m', 0),
                    'precipitation': rain_mm,
                    'pressure': cur.get('surface_pressure', 1012),
                    'uv_index': uv_max,
                    'condition': cond_text,
                    'icon': cond_icon
                },
                'advisories': {
                    'irrigation': irrigation_adv,
                    'spraying': spraying_adv,
                    'harvesting': 'Good window for harvesting and post-harvest drying.' if rain_mm == 0 else 'Keep harvested produce covered under dry shelter.'
                },
                'forecast': forecast_days
            }
        except Exception as e:
            print(f"[AgroConnect Weather] Error: {e}")
            return None

    def reverse_geocode(lat, lon):
        """Convert GPS coordinates into real city, district, state and country name."""
        # 1. Try BigDataCloud reverse geocode client
        try:
            url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
            req = urllib.request.Request(url, headers={'User-Agent': 'AgroConnect/1.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                locality = data.get('locality')
                city = data.get('city')
                state = data.get('principalSubdivision')
                country = data.get('countryName')
                parts = []
                if locality and locality != city:
                    parts.append(locality)
                if city:
                    parts.append(city)
                if state and state not in parts:
                    parts.append(state)
                if country:
                    parts.append(country)
                if parts:
                    return ", ".join(parts)
        except Exception as e:
            print(f"[AgroConnect ReverseGeocode] BigDataCloud: {e}")
            
        # 2. Try OpenStreetMap Nominatim
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
            req = urllib.request.Request(url, headers={'User-Agent': 'AgroConnectApp/1.0 (contact@agroconnect.local)'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                addr = data.get('address', {})
                town = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county') or addr.get('state_district')
                state = addr.get('state')
                country = addr.get('country')
                parts = [p for p in [town, state, country] if p]
                if parts:
                    return ", ".join(parts)
        except Exception as e:
            print(f"[AgroConnect ReverseGeocode] Nominatim: {e}")
            
        return None

    def geocode_location(query):
        try:
            encoded = urllib.parse.quote(query.strip())
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1&language=en&format=json"
            req = urllib.request.Request(url, headers={'User-Agent': 'AgroConnect/1.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                results = data.get('results', [])
                if results:
                    r = results[0]
                    name = r.get('name')
                    admin1 = r.get('admin1', '')
                    country = r.get('country', '')
                    disp = f"{name}" + (f", {admin1}" if admin1 else "") + (f", {country}" if country else "")
                    return float(r.get('latitude')), float(r.get('longitude')), disp
        except Exception as e:
            print(f"[AgroConnect Geocode] Error: {e}")
        return None

    @app.route('/api/weather', methods=['GET'])
    def get_weather():
        city = request.args.get('city')
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        
        # 1. Direct coordinates
        if lat and lon:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                name = request.args.get('name')
                if not name or name.strip().lower() in ['my gps location', 'local farm', '']:
                    real_name = reverse_geocode(lat_f, lon_f)
                    name = real_name if real_name else f"{lat_f:.2f}°, {lon_f:.2f}°"
                w_data = fetch_live_weather(lat_f, lon_f, name)
                if w_data:
                    return jsonify(w_data)
            except (ValueError, TypeError):
                pass
                
        # 2. City query
        if city:
            geo = geocode_location(city)
            if geo:
                lat_f, lon_f, disp = geo
                w_data = fetch_live_weather(lat_f, lon_f, disp)
                if w_data:
                    return jsonify(w_data)
                    
        # 3. Logged-in user location
        if current_user.is_authenticated and (current_user.district or current_user.village):
            q = current_user.district or current_user.village
            geo = geocode_location(q)
            if geo:
                lat_f, lon_f, disp = geo
                loc_label = f"{current_user.village}, {disp}" if current_user.village and current_user.village not in disp else disp
                w_data = fetch_live_weather(lat_f, lon_f, loc_label)
                if w_data:
                    return jsonify(w_data)
                    
        # 4. Default to Pune, Maharashtra
        w_data = fetch_live_weather(18.5204, 73.8567, "Pune, Maharashtra, India")
        if w_data:
            return jsonify(w_data)
            
        return jsonify({'success': False, 'message': 'Weather service temporarily unavailable'}), 503

    # --- ANALYSIS SAVE (Stores in Dedicated Relational Tables) ---
    @app.route('/api/analysis/save', methods=['POST'])
    @login_required
    def save_analysis():
        data = request.get_json() or {}
        analysis_type = data.get('type')
        results = data.get('results', {})
        inputs = data.get('inputs', {})
        
        # Server-side validation for 'Field & Soil Metrics'
        if analysis_type == 'Field & Soil Metrics':
            farm_size = inputs.get('farm_size')
            soil = inputs.get('soil')
            water = inputs.get('water')
            
            if not farm_size:
                return jsonify({'success': False, 'message': 'Farm Size must be a positive number.'}), 400
            try:
                if float(farm_size) <= 0:
                    return jsonify({'success': False, 'message': 'Farm Size must be a positive number.'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Farm Size must be a positive number.'}), 400
                
            if soil not in ['black', 'alluvial', 'red', 'sandy']:
                return jsonify({'success': False, 'message': 'Invalid Soil Type.'}), 400
                
            if water not in ['rain', 'tubewell', 'canal']:
                return jsonify({'success': False, 'message': 'Invalid Water Source.'}), 400

            metric = FieldSoilMetric(
                user_id=current_user.id,
                farm_size=float(farm_size),
                soil_type=soil,
                water_source=water,
                recommended_crop=results.get('recommended_crop', 'Wheat'),
                seed_bags=int(results.get('seed_bags', 10)),
                water_need=results.get('water_need', 'Medium')
            )
            db.session.add(metric)
            db.session.commit()
            return jsonify({'success': True})

        elif analysis_type == 'Crop Recommendation':
            rec = CropRecommendation(
                user_id=current_user.id,
                nitrogen=float(inputs.get('nitrogen', inputs.get('n', 0))) if (inputs.get('nitrogen') or inputs.get('n')) else None,
                phosphorus=float(inputs.get('phosphorus', inputs.get('p', 0))) if (inputs.get('phosphorus') or inputs.get('p')) else None,
                potassium=float(inputs.get('potassium', inputs.get('k', 0))) if (inputs.get('potassium') or inputs.get('k')) else None,
                temperature=float(inputs.get('temperature', inputs.get('temp', 0))) if (inputs.get('temperature') or inputs.get('temp')) else None,
                humidity=float(inputs.get('humidity', inputs.get('hum', 0))) if (inputs.get('humidity') or inputs.get('hum')) else None,
                ph=float(inputs.get('ph', 6.5)) if inputs.get('ph') else None,
                rainfall=float(inputs.get('rainfall', inputs.get('rain', 0))) if (inputs.get('rainfall') or inputs.get('rain')) else None,
                season=inputs.get('season'),
                soil_type=inputs.get('soil', inputs.get('soil_type')),
                recommended_crop=results.get('recommended_crop', 'Rice'),
                confidence=results.get('confidence', '95%'),
                reason=results.get('reason', ''),
                sowing_time=results.get('sowing_time', results.get('time', 'Seasonal'))
            )
            db.session.add(rec)
            db.session.commit()
            return jsonify({'success': True})

        elif analysis_type == 'Soil Health':
            record = SoilHealthRecord(
                user_id=current_user.id,
                ph=float(inputs.get('ph', 6.5)),
                nitrogen=float(inputs.get('nitrogen', 0)) if inputs.get('nitrogen') else None,
                phosphorus=float(inputs.get('phosphorus', 0)) if inputs.get('phosphorus') else None,
                potassium=float(inputs.get('potassium', 0)) if inputs.get('potassium') else None,
                organic_carbon=float(inputs.get('organic_carbon', 0)) if inputs.get('organic_carbon') else None,
                status=results.get('status', 'Optimal & Healthy'),
                fertilizer_recommendation=results.get('fert', results.get('fertilizer_recommendation', 'Standard NPK'))
            )
            db.session.add(record)
            db.session.commit()
            return jsonify({'success': True})

        elif analysis_type == 'Yield Prediction':
            raw_yield = results.get('total_yield', 0)
            if isinstance(raw_yield, str):
                raw_yield = raw_yield.replace('Quintals', '').replace('Tons', '').replace('tonnes', '').replace('T', '').strip()
            try:
                total_yield_val = float(raw_yield)
            except (ValueError, TypeError):
                total_yield_val = 0.0

            raw_profit = results.get('profit', 0)
            if isinstance(raw_profit, str):
                raw_profit = raw_profit.replace('₹', '').replace(',', '').strip()
            try:
                profit_val = float(raw_profit)
            except (ValueError, TypeError):
                profit_val = 0.0

            farm_size_val = inputs.get('size', inputs.get('farm_size', current_user.farm_size or 5.0))
            try:
                farm_size_val = float(farm_size_val)
            except (ValueError, TypeError):
                farm_size_val = 5.0

            yp = YieldPrediction(
                user_id=current_user.id,
                crop=inputs.get('crop', current_user.primary_crop or 'Wheat'),
                farm_size=farm_size_val,
                season=inputs.get('season'),
                total_yield=total_yield_val,
                profit=profit_val,
                duration_days=results.get('duration', results.get('duration_days', '120 Days')),
                quality_grade=results.get('quality', results.get('quality_grade', 'Grade A'))
            )
            db.session.add(yp)
            db.session.commit()
            return jsonify({'success': True})

        elif analysis_type == 'Irrigation Plan':
            farm_size_val = inputs.get('size', inputs.get('farm_size', current_user.farm_size or 5.0))
            try:
                farm_size_val = float(farm_size_val)
            except (ValueError, TypeError):
                farm_size_val = None

            plan = IrrigationPlan(
                user_id=current_user.id,
                farm_size=farm_size_val,
                soil_type=inputs.get('soil', inputs.get('soil_type')),
                water_source=inputs.get('source', inputs.get('water_source')),
                temperature=float(inputs.get('temp', 0)) if inputs.get('temp') else None,
                rain_chance=float(inputs.get('rainChance', 0)) if inputs.get('rainChance') else None,
                wind_speed=float(inputs.get('windSpeed', 0)) if inputs.get('windSpeed') else None,
                frequency=results.get('freq', results.get('frequency', 'Every 3 Days')),
                warning=results.get('warning', 'Monitor soil moisture regularly.'),
                water_need=results.get('water_need', 'Moderate')
            )
            db.session.add(plan)
            db.session.commit()
            return jsonify({'success': True})

        return jsonify({'success': False, 'message': 'Unknown analysis type'}), 400

    # --- GET REPORTS (Consolidated across Relational Tables) ---
    @app.route('/api/reports', methods=['GET'])
    @login_required
    def get_reports():
        # Query all relational tables
        crops = CropRecommendation.query.filter_by(user_id=current_user.id).all()
        soils = SoilHealthRecord.query.filter_by(user_id=current_user.id).all()
        yields = YieldPrediction.query.filter_by(user_id=current_user.id).all()
        irrigations = IrrigationPlan.query.filter_by(user_id=current_user.id).all()
        fields = FieldSoilMetric.query.filter_by(user_id=current_user.id).all()
        
        all_items = crops + soils + yields + irrigations + fields
        # Sort by creation date descending
        all_items.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        
        report_list = []
        for item in all_items:
            d = item.to_dict()
            # Support both {input, output} and {inputs, results} keys for frontend components
            d['inputs'] = d.get('input', {})
            d['results'] = d.get('output', {})
            # Remove datetime object before serializing
            d.pop('created_at', None)
            report_list.append(d)
            
        return jsonify({'success': True, 'reports': report_list})

    # --- ANALYTICS SUMMARY (Direct SQL Table Aggregations) ---
    @app.route('/api/analytics/summary', methods=['GET'])
    @login_required
    def get_analytics_summary():
        # Field & Soil Metrics data
        field_records = FieldSoilMetric.query.filter_by(user_id=current_user.id).all()
        soil_data = [{'farm_size': f.farm_size, 'soil': f.soil_type.lower()} for f in field_records]
        water_data = [{'farm_size': f.farm_size, 'water': f.water_source.lower()} for f in field_records]
        
        # Yield Predictions data
        yield_records = YieldPrediction.query.filter_by(user_id=current_user.id).order_by(YieldPrediction.created_at.asc()).all()
        roi_data = []
        yield_trend_data = []
        
        for y in yield_records:
            date_str = y.created_at.strftime('%Y-%m-%d %H:%M:%S') if y.created_at else ''
            roi_data.append({
                'farm_size': y.farm_size,
                'crop': y.crop,
                'profit': y.profit
            })
            yield_trend_data.append({
                'farm_size': y.farm_size,
                'date': date_str,
                'total_yield': y.total_yield
            })
            
        return jsonify({
            'success': True,
            'soil_data': soil_data,
            'water_data': water_data,
            'roi_data': roi_data,
            'yield_trend_data': yield_trend_data
        })

    # Initialize tables and seed dummy records
    seed_dummy_database(app)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
