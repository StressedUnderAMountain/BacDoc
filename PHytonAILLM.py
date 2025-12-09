import pandas as pd
import re
from difflib import get_close_matches
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_session import Session
from datetime import timedelta, datetime
import os

def load_data_safe(filepath="Centraldatabase.csv"):
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file {filepath} is missing.")
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()  # Return empty DataFrame on failure

data = load_data_safe()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'bacdoc_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
app.permanent_session_lifetime = timedelta(minutes=30)
Session(app)

USER_CREDENTIALS = {'admin': 'bacdoc123'}
BRAND_NAME = "BacDoc Microbiology Assistant"

def extract_intent(user_input):
    user_input = user_input.lower()
    if any(phrase in user_input for phrase in ['how to grow', 'grow', 'growing', 'cultivation', 'culture']):
        return 'growth'
    elif any(phrase in user_input for phrase in ['how to identify', 'identify', 'identification', 'differentiate', 'distinguish', 'isolate', 'isolation']):
        return 'isolation'
    elif any(word in user_input for word in ['media']):
        return 'media'
    else:
        return 'full'

def find_organism(user_input):
    user_input = user_input.lower()
    for org in data['Organism']:
        if org.lower() in user_input:
            return org
    return None

def scale_composition(comp_str, volume_ml):
    if pd.isna(comp_str) or not comp_str.strip() or comp_str.strip().lower() == 'unknown':
        return "No composition info available."
    
    if ';' in comp_str:
        parts = comp_str.split(';')
    else:
        parts = comp_str.split(',')
    
    scaled_parts = []
    for part in parts:
        token = part.strip()
        match = re.search(r'([\d\.]+)\s*([a-zA-Z%]+)', token)
        if match:
            num = float(match.group(1))
            unit = match.group(2).lower()
            
            if unit in ['g', 'mg']:
                scaled_num = num * volume_ml / 100
                if 0 < scaled_num < 0.01:
                    scaled_str = f"{scaled_num:.4f}{unit if unit == 'g' else 'g'}"
                else:
                    scaled_str = f"{scaled_num:.2f}{unit if unit == 'g' else 'g'}"
                token = re.sub(r'([\d\.]+)\s*[a-zA-Z%]+', scaled_str, token, count=1)
            elif unit in ['ml']:
                scaled_num = num * volume_ml / 100
                scaled_str = f"{scaled_num:.2f}ml"
                token = re.sub(r'([\d\.]+)\s*[a-zA-Z%]+', scaled_str, token, count=1)
            elif unit in ['l']:
                scaled_num = num * volume_ml / 100
                scaled_str = f"{scaled_num:.4f}l"
                token = re.sub(r'([\d\.]+)\s*[a-zA-Z%]+', scaled_str, token, count=1)
        scaled_parts.append(token)
    
    return "; ".join(scaled_parts)

def parse_composition(comp_str):
    comp_dict = {}
    if not comp_str or pd.isna(comp_str) or comp_str.strip().lower() == 'unknown' or comp_str == "No composition info available.":
        return comp_dict
    
    if ';' in comp_str:
        parts = comp_str.split(';')
    else:
        parts = comp_str.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Try to match: component name + number + unit
        match = re.search(r'([^:\d]+?)\s*:?\s*([\d\.]+)\s*([a-zA-Z%]*)', part, re.I)
        if match:
            name = match.group(1).strip().lower().rstrip(':').strip()
            amount_str = match.group(2)
            unit = match.group(3).lower() if match.group(3) else 'g'
            
            # Skip water and pH entries
            if any(skip_word in name for skip_word in ['ph', 'water', 'distilled']):
                continue
            
            try:
                amount = float(amount_str)
            except ValueError:
                continue
            
            # Unit conversion
            if unit in ['mg']:
                amount /= 1000
                unit = 'g'  # Convert to grams for consistency
            elif unit in ['%']:
                pass  # Keep as percentage
            elif unit in ['ml', 'l']:
                pass  # Keep ml/l units
            else:
                unit = 'g'  # Default to grams
            
            name = re.sub(r'\s+', ' ', name).strip()
            if name and len(name) > 1:
                comp_dict[name] = {'amount': amount, 'unit': unit}
        else:
            # No numeric match - this is a qualitative component (e.g., "with selective antibiotics")
            # Add it with a special marker
            clean_part = part.lower().strip()
            if clean_part and len(clean_part) > 2:
                comp_dict[clean_part] = {'amount': None, 'unit': 'supplement'}
    
    return comp_dict

def parse_temp_ph(optimal_growth_conditions):
    temp = None
    ph = None
    if isinstance(optimal_growth_conditions, str):
        temp_match = re.search(r'(\d+\.?\d*)\s*°?C', optimal_growth_conditions)
        if temp_match:
            temp = float(temp_match.group(1))
        ph_match = re.search(r'pH\s*(\d+\.?\d*)', optimal_growth_conditions, re.I)
        if ph_match:
            ph = float(ph_match.group(1))
    return temp, ph

def clean_param(value):
    if not isinstance(value, str):
        return ''
    return value.strip().lower()

def param_match_score(row_val, user_val):
    if not user_val:
        return 0
    if not isinstance(row_val, str):
        return 1
    return 0 if clean_param(row_val) == clean_param(user_val) else 1

def get_closest_matches_extended(origin, temp_input, ph_input, aerobicity, morphology, gramnature, n=5):
    origin_clean = clean_param(origin)
    aerobicity_clean = clean_param(aerobicity)
    morphology_clean = clean_param(morphology)
    gramnature_clean = clean_param(gramnature)
    
    print(f"\n{'='*80}")
    print(f"SEARCH PARAMETERS:")
    print(f"Origin: '{origin_clean}' | Temp: {temp_input}°C | pH: {ph_input}")
    print(f"Aerobicity: '{aerobicity_clean}' | Morphology: '{morphology_clean}' | Gram: '{gramnature_clean}'")
    print(f"{'='*80}\n")
    
    # Parse user inputs
    try:
        temp_val = float(re.sub(r'[^\d\.]', '', str(temp_input)))
    except Exception:
        temp_val = None
    try:
        ph_val = float(re.sub(r'[^\d\.]', '', str(ph_input)))
    except Exception:
        ph_val = None
    
    matches = []

    for idx, row in data.iterrows():
        organism_name = row.get('Organism', 'Unknown')
        
        # === SMART MULTI-VALUE PARSING ===
        def parse_numeric_range(raw_value):
            """Parse multiple values: "37,39,40,42" → [37.0, 39.0, 40.0, 42.0]"""
            if not isinstance(raw_value, str) or not raw_value.strip():
                return None
            
            values = [v.strip() for v in raw_value.split(',') if v.strip()]
            if not values:
                return None
            
            numbers = []
            for val in values:
                clean = re.sub(r'[^\d\.]', '', val)
                try:
                    numbers.append(float(clean))
                except:
                    pass
            
            return numbers if numbers else None

        def parse_category_range(raw_value):
            """Parse categories: "Facultative anaerobe, 5% CO2" → "facultative anaerobe" """
            if not isinstance(raw_value, str) or not raw_value.strip():
                return ''
            
            first_part = raw_value.split(',')[0].strip()
            return clean_param(first_part)

        # Get CSV values using smart parsing
        temp_csv_list = parse_numeric_range(row.get('Optimal Growth Temperature (°C)', ''))
        ph_csv_list = parse_numeric_range(row.get('Optimal Growth pH', ''))
        origin_csv = clean_param(str(row.get('Origin/Source', '')))
        aerobicity_csv = parse_category_range(row.get('Optimal Growth Aerobic Conditions', ''))
        morphology_csv = clean_param(str(row.get('Morphology', '')))
        gram_csv = clean_param(str(row.get('Gram Nature', '')))
        
        # === BACDOC EQUATION 2 + FULL PENALTIES ===
        
        # Temperature: W1 × |ΔTemp| (Penalty=20×W1)
        if temp_val is not None and temp_csv_list:
            # Find closest temperature in range
            d_temp = min(abs(temp_val - t) for t in temp_csv_list) * 5  # W1=5
            temp_csv = f"{temp_csv_list[0]}"  # For display
        else:
            d_temp = 20 * 5  # Penalty × W1=100
            temp_csv = None
        
        # pH: W2 × |ΔpH| (Penalty=10×W2)
        if ph_val is not None and ph_csv_list:
            # Find closest pH in range
            d_ph = min(abs(ph_val - p) for p in ph_csv_list) * 5  # W2=5
            ph_csv = f"{ph_csv_list[0]}"  # For display
        else:
            d_ph = 10 * 5  # Penalty × W2=50
            ph_csv = None
        
        # Origin: W3 × match (Penalty=5×W3)
        if origin_clean and origin_clean in origin_csv:
            origin_score = 0 * 2  # Perfect match
        elif origin_clean:  # User gave origin, CSV empty
            origin_score = 5 * 2  # Penalty × W3=10
        else:
            origin_score = 1 * 2  # Mismatch
        
        # Aerobicity: W4 × match (Penalty=4×W4)
        if aerobicity_clean == aerobicity_csv and aerobicity_csv:
            aerobicity_score = 0 * 4  # Perfect match
        elif aerobicity_csv:  # Mismatch
            aerobicity_score = 1 * 4  # W4=4
        else:  # No CSV data
            aerobicity_score = 4 * 4  # Penalty × W4=16
        
        # Morphology: W5 × match (Penalty=3×W5)
        if morphology_clean == morphology_csv and morphology_csv:
            morphology_score = 0 * 2  # Perfect match
        elif morphology_csv:  # Mismatch
            morphology_score = 1 * 2  # W5=2
        else:  # No CSV data
            morphology_score = 3 * 2  # Penalty × W5=6
        
        # Gram: W6 × match (Penalty=3×W6)
        if gramnature_clean == gram_csv and gram_csv:
            gram_score = 0 * 2  # Perfect match
        elif gram_csv:  # Mismatch
            gram_score = 1 * 2  # W6=2
        else:  # No CSV data
            gram_score = 3 * 2  # Penalty × W6=6
        
        # Equation 2: Σ Weighted distances + Penalties
        dist = d_temp + d_ph + origin_score + aerobicity_score + morphology_score + gram_score
        
        # Debug output for first 10 organisms
        if idx < 10:
            print(f"{organism_name[:30]:30} | CSV: T={temp_csv}, pH={ph_csv}, O='{origin_csv[:15]}', A='{aerobicity_csv[:10]}', M='{morphology_csv[:10]}', G='{gram_csv[:8]}'")
            print(f"{'':30} | Scores: temp={d_temp:.1f}, pH={d_ph:.1f}, origin={origin_score}, aero={aerobicity_score}, morph={morphology_score}, gram={gram_score} | TOTAL={dist:.1f}")
            print()
        
        matches.append((dist, row))
    
    # Sort by distance (ascending - lower is better)
    matches.sort(key=lambda x: x[0])
    
    print(f"DEBUG: {organism_name} distance={dist:.1f}")  # Single debug line

    
    # Return top N matches
    return [m[1] for m in matches[:n]]


def is_valid_media(row):
    comp = row.get('Optimal Media Composition (per 100ml)', '')
    invalid_entries = ['', 'unknown', '-', None, 'same as optimal media']
    if isinstance(comp, str):
        comp_lower = comp.strip().lower()
        return comp_lower not in invalid_entries
    return False

def merge_compositions_detailed(rows, volume_ml=100):
    all_compositions = {}
    component_sources = {}
    colors = ['#FF6B6B', "#FFC800", "#88FF00", "#00F1D5", "#008FE8", "#BC75EB", "#FFFFFF", "#000000"]
    
    for i, row in enumerate(rows):
        comp = row.get('Optimal Media Composition (per 100ml)', '')
        if pd.isna(comp) or not comp.strip() or comp.strip().lower() == 'unknown':
            continue
        
        scaled_comp = scale_composition(comp, volume_ml)
        comp_dict = parse_composition(scaled_comp)
        organism_name = row.get('Organism', 'Unknown')
        media_name = row.get('Optimal Media', 'Unknown Media')
        color = colors[i % len(colors)]
        
        for component, data in comp_dict.items():
            # Handle new format: {'amount': X, 'unit': 'g'}
            if isinstance(data, dict):
                amount = data.get('amount')
                unit = data.get('unit', 'g')
            else:
                # Backward compatibility: old format was just a number
                amount = data
                unit = 'g'
            
            # Skip supplements without numeric amounts
            if amount is None or unit == 'supplement':
                continue
            
            if component in all_compositions:
                all_compositions[component]['amounts'].append(amount)
                all_compositions[component]['unit'] = unit  # Keep the unit
                component_sources[component].append({
                    'organism': organism_name,
                    'media': media_name,
                    'amount': amount,
                    'unit': unit,
                    'color': color
                })
            else:
                all_compositions[component] = {'amounts': [amount], 'unit': unit}
                component_sources[component] = [{
                    'organism': organism_name,
                    'media': media_name,
                    'amount': amount,
                    'unit': unit,
                    'color': color
                }]
    
    # Average the amounts and format with units
    averaged_compositions = {}
    detailed_sources = {}
    for component, data in all_compositions.items():
        amounts = data['amounts']
        unit = data['unit']
        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            averaged_compositions[component] = {'amount': avg_amount, 'unit': unit}
            detailed_sources[component] = component_sources[component]
    
    return averaged_compositions, detailed_sources

def suggest_organisms(user_input, cutoff=0.6, max_suggestions=5):
    # Get unique organism list (remove duplicates, preserve order)
    organism_list = []
    seen = set()
    for org in data['Organism']:
        if org not in seen:
            organism_list.append(org)
            seen.add(org)
    
    matches = get_close_matches(user_input, organism_list, n=max_suggestions, cutoff=cutoff)
    return matches

def extract_organism_from_query(user_input):
    user_input = user_input.lower()
    prefixes_to_remove = [
        'how to grow', 'how to identify', 'how to isolate', 'how to culture',
        'grow', 'identify', 'isolate', 'culture', 'cultivation of'
    ]
    cleaned_input = user_input
    for prefix in prefixes_to_remove:
        if cleaned_input.startswith(prefix):
            cleaned_input = cleaned_input[len(prefix):].strip()
            break
    return cleaned_input

@app.route('/')
def home():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', page='home', brand_name=BRAND_NAME)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
            session['logged_in'] = True
            session['login_time'] = datetime.now()
            return redirect(url_for('home'))
        else:
            return render_template('index.html', page='login', error='Invalid credentials')
    return render_template('index.html', page='login')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/get_organism_info', methods=['POST'])
def get_organism_info():
    try:
        if 'logged_in' not in session:
            return jsonify({"success": False, "error": "Not logged in."})
        
        data_json = request.get_json()
        organism_input = data_json.get('organism_name', '').strip()
        volume = data_json.get('volume', 100)
        preserve_intent = data_json.get('preserve_intent', False)
        original_intent = data_json.get('original_intent', None)
        
        if preserve_intent and original_intent:
            intent = original_intent
        else:
            intent = extract_intent(organism_input)
        
        org_name = extract_organism_from_query(organism_input)
        found_org = find_organism(org_name)
        
        if found_org:
            info = data[data['Organism'] == found_org].iloc[0]
            try:
                vol_float = float(volume)
                if vol_float <= 0:
                    vol_float = 100
            except Exception:
                vol_float = 100
            
            if intent == 'growth':
                media_comp = info.get('Optimal Media Composition (per 100ml)', '')
                bio_tests = []
                show_all_fields = False
            elif intent == 'isolation':
                media_comp = info.get('Differential Media Composition', '')
                bio_tests = info.get('Biochemical Test', '').split(',') if info.get('Biochemical Test') else []
                show_all_fields = False
            else:  # Full info when just organism name
                media_comp = info.get('Optimal Media Composition (per 100ml)', '')
                bio_tests = info.get('Biochemical Test', '').split(',') if info.get('Biochemical Test') else []
                show_all_fields = True
            
            scaled_comp = scale_composition(media_comp, vol_float)
            comp_dict = parse_composition(scaled_comp)
            
            response_data = {
                "organism_name": found_org,
                "origin": info.get('Origin/Source', 'N/A'),
                "growth_conditions": f"{info.get('Optimal Growth Temperature (°C)', 'N/A')}°C, pH {info.get('Optimal Growth pH', 'N/A')}",
                "media_composition": comp_dict,
                "biochemical_tests": [test.strip() for test in bio_tests if test.strip()],
                "volume": vol_float,
                "intent": intent,
                "show_all_fields": show_all_fields,
                "is_unknown": False
            }
            
            if show_all_fields:
                optimal_media = info.get('Optimal Media Composition (per 100ml)', '')
                differential_media = info.get('Differential Media Composition', '')
                optimal_media_dict = parse_composition(scale_composition(optimal_media, vol_float))
                differential_media_dict = parse_composition(scale_composition(differential_media, vol_float))
                response_data["optimal_media_composition"] = optimal_media_dict
                response_data["differential_media_composition"] = differential_media_dict
                response_data["optimal_media_name"] = info.get("Optimal Media", "")
                response_data["differential_media_name"] = info.get("Differential Media", "")
                response_data["biochemical_tests"] = [test.strip() for test in info.get("Biochemical Test",'').split(',') if test.strip()]
            
            return jsonify({"success": True, "data": response_data})
        else:
            suggestions = suggest_organisms(org_name)
            return jsonify({
                "success": False,
                "error": "Organism not found. Is it an unknown organism?",
                "suggestions": suggestions
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Internal server error: {e}"})

@app.route('/suggest_organisms', methods=['POST'])
def suggest_organisms_api():
    data_json = request.get_json()
    partial = data_json.get('partial', '').lower()
    cleaned_partial = extract_organism_from_query(partial)
    
    # Get matching organisms and remove duplicates while preserving order
    suggestions = []
    seen = set()
    for org in data['Organism']:
        if cleaned_partial in org.lower() and org not in seen:
            suggestions.append(org)
            seen.add(org)
            if len(suggestions) >= 8:
                break
    
    return jsonify({'suggestions': suggestions})

@app.route('/unknown_result_ajax', methods=['POST'])
def unknown_result_ajax():
    if 'logged_in' not in session:
        return jsonify({"success": False, "error": "Not logged in."})
    
    req = request.get_json()
    origin = req.get('origin')
    temperature = req.get('temperature')
    ph = req.get('ph')
    aerobicity = req.get('aerobicity')
    morphology = req.get('morphology')
    gram = req.get('gram')
    volume = req.get('volume', 100)
    
    try:
        vol_float = float(volume)
        if vol_float <= 0:
            vol_float = 100
    except Exception:
        vol_float = 100
    
    matched_rows = get_closest_matches_extended(origin, temperature, ph, aerobicity, morphology, gram, n=5)
    valid_rows = [row for row in matched_rows if is_valid_media(row)]
    
    if valid_rows:
        merged_dict, detailed_sources = merge_compositions_detailed(valid_rows, vol_float)
        contributors = []
        for i, row in enumerate(valid_rows[:5]):
            org = row.get('Organism', 'Unknown')
            media = row.get('Optimal Media', 'Unknown Media')
            contributors.append({
                'organism': org,
                'media': media,
                'color': ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57'][i % 5]
            })
        
        response_data = {
            "organism_name": f"Unknown Organism (based on {len(valid_rows)} similar organisms)",
            "origin": f"User input: {origin}",
            "growth_conditions": f"{temperature}°C, pH {ph}, {aerobicity}, {morphology}, {gram}",
            "media_composition": merged_dict,
            "component_sources": detailed_sources,
            "contributors": contributors,
            "biochemical_tests": [],
            "volume": vol_float,
            "intent": 'growth',
            "show_all_fields": False,
            "is_unknown": True
        }
        return jsonify({"success": True, "data": response_data})
    else:
        return jsonify({"success": False, "error": "No suitable media found for these parameters."})

@app.before_request
def make_session_permanent():
    session.permanent = True
    if 'logged_in' in session:
        login_time = session.get('login_time')
        if login_time:
            elapsed = datetime.now() - login_time
            if elapsed > app.permanent_session_lifetime:
                session.clear()
                return redirect(url_for('login'))
        else:
            session['login_time'] = datetime.now()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)