from flask import Flask, request, redirect, render_template
from fhirclient import client
import requests

app = Flask(__name__)

# Epic FHIR R4 sandbox settings
EPIC_FHIR_R4_URL = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
CLIENT_ID = "09f4c53c-d958-4c53-b2b2-f78c6f1f543d"
CLIENT_SECRET = "lfNCYW41UmP67mICULKriHeke7uj8RMJZzz7ZsUd+ANxb7em+3aUnuf7EtuVAdETy/+JcqDz5/wdywztb64xpQ=="
REDIRECT_URI = "http://localhost:5000/callback"

# FHIR client settings
settings = {
    'app_id': CLIENT_ID,
    'api_base': EPIC_FHIR_R4_URL,
    'redirect_uri': REDIRECT_URI,
    'scope': 'launch/patient Patient.read Patient.search openid fhirUser'
}

smart = client.FHIRClient(settings=settings)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return redirect(smart.authorize_url)

@app.route('/callback')
def callback():
    try:
        code = request.args.get('code')
        if not code:
            raise ValueError("Authorization code not found")

        token_response = requests.post(
            "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': REDIRECT_URI,
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
            },
        )
        token_response.raise_for_status()
        token_json = token_response.json()

        headers = {
            'Authorization': f"Bearer {token_json['access_token']}",
            "Accept": "application/json"
        }
        patient_response = requests.get(f"{EPIC_FHIR_R4_URL}/Patient", headers=headers)
        patient_response.raise_for_status()
        patient_data = patient_response.json()

        if not patient_data.get('entry'):
            raise ValueError("No patient data found")

        patient_resource = patient_data['entry'][0]['resource']
        patient_id = patient_resource['id']

        endpoints = {
            'allergies': f"{EPIC_FHIR_R4_URL}/AllergyIntolerance?patient={patient_id}",
            'medications': f"{EPIC_FHIR_R4_URL}/MedicationRequest?patient={patient_id}",
            'conditions': f"{EPIC_FHIR_R4_URL}/Condition?patient={patient_id}",
        }

        responses = {}
        for key, url in endpoints.items():
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            responses[key] = response.json().get('entry', [])

        return render_template(
            'patient.html',
            patient=patient_resource,
            allergies=responses['allergies'],
            medications=responses['medications'],
            conditions=responses['conditions'],
        )

    except Exception as e:
        app.logger.error(f"An error occurred: {str(e)}", exc_info=True)
        return render_template('error.html', error_message=str(e))

if __name__ == '__main__':
    app.run(debug=True)