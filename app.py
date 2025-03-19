from flask import Flask, jsonify, url_for, render_template, request
import os
from dotenv import load_dotenv
import psycopg2
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_cors import CORS
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import id_token

load_dotenv()

app = Flask(__name__)

# Permite CORS para todos los orígenes (esto es útil para desarrollo)
CORS(app)



def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT")
    )
    return conn



@app.route('/projects', methods=['GET','POST'])
def handle_projects():
    if request.method == 'GET':
        # Leer la tabla PROJECT_MSTR y retornar la lista
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT * FROM PROJECT_MSTR ORDER BY PROJECT_ID ASC")
            rows = cur.fetchall()
            cur.close()
            conn.close()

            # Convertir filas en JSON
            projects = []
            for r in rows:
                projects.append({
                    "PROJECT_ID": r["project_id"],
                    "PROJECT_NAME": r["project_name"]
                })
            return jsonify(projects), 200
        except Exception as e:
            print("Error GET /projects:", e)
            return jsonify({"error": str(e)}), 500

    elif request.method == 'POST':
        # Crear un proyecto nuevo
        data = request.get_json()
        proj_name = data.get("PROJECT_NAME", "")

        if not proj_name:
            return jsonify({"error": "PROJECT_NAME is required"}), 400

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            insert_sql = """
                INSERT INTO PROJECT_MSTR (PROJECT_NAME)
                VALUES (%s)
                RETURNING PROJECT_ID
            """
            cur.execute(insert_sql, (proj_name,))
            new_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()

            # Retornamos el objeto creado
            created_project = {
                "PROJECT_ID": new_id,
                "PROJECT_NAME": proj_name
            }
            return jsonify(created_project), 201

        except Exception as e:
            print("Error POST /projects:", e)
            return jsonify({"error": str(e)}), 500


@app.route('/sendEmailToValidateVerification',  methods=['POST'])
def sendVerificationCode():
    sender_email = os.getenv('GMAIL_ACCOUNT')  # Tu correo de Gmail
    sender_password = os.getenv('GMAIL_PASSWORD')   # Contraseña de tu correo o contraseña de aplicación
    data = request.get_json()
    recipient_email = data.get('email')
    verification_code = data.get('code')

     #Convertir el array a la forma "XX - XXXX - XX"
    formatted_code = format_code(verification_code)

    print("Le correo es:" +  recipient_email)
    print("el codigo es: " + str(formatted_code))
    # Configuración del mensaje
    subject = "Código de Verificación"
    body = f"""
    <div style="width: 100%; height: 50px">
    <h1>Hola, Espero estés bien:)</h1>
    </div>
    
    <div style="width: 100%; height: 200px; display:flex; flex-direction: column; justify-content: center; align-items: center; background-color: rgb(243, 243, 243);">
    <h3>Tu Código de Verificación es:</h3>
     <strong>{formatted_code}</strong>
    </div>
   
    
    """

    # Crear el mensaje
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Adjuntar el cuerpo del mensaje
    msg.attach(MIMEText(body, 'html'))

    try:
        # Conectar al servidor SMTP de Gmail
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)  # Iniciar sesión en Gmail
        text = msg.as_string()

        # Enviar el correo
        server.sendmail(sender_email, recipient_email, text)
        server.quit()  # Cerrar la conexión

        return {"data": formatted_code}
    except Exception as e:
        return f"Error al enviar el correo: {e}"



def format_code(code_array):
    # Asegurarse de que el array tiene la longitud correcta (por ejemplo, [xx, xxxx, xx])
    if len(code_array) == 8:
        # Formatear el array como "XX - XXXX - XX"
        formatted_code = f"{code_array[0]}{code_array[1]} - {code_array[2]}{code_array[3]}{code_array[4]}{code_array[5]} - {code_array[6]}{code_array[7]}"
        return formatted_code
    else:
        return "Código inválido"  # En caso de que el formato del array no sea el esperado
    
    
    
    
    # A PARTIR DE AQUI ESTÁ LA PARTE DE LOGEO Y REGSTRO CON GOOGLE ------------------------------------------------------------
    # Sustituye esto con tu propio Client ID que obtuviste de Google Cloud Console
CLIENT_ID = os.getenv('CLIENT_GOOGLE_ID')

@app.route('/login-with-google', methods=['POST'])
def login_with_google():
    data = request.get_json()
    id_token_from_client = data.get('token')  # Token enviado desde el cliente

    try:
        # Verificar el token de Google
        id_info = id_token.verify_oauth2_token(id_token_from_client, Request(), CLIENT_ID)

        # Extraer la información del token (correo, ID de Google, etc.)
        email = id_info['email']
        google_id = id_info['sub']
        first_name = id_info.get('given_name', 'N/A')
        last_name = id_info.get('family_name', 'N/A')

        # Aquí puedes verificar si el usuario existe en tu base de datos.
        # Si no existe, puedes registrar al usuario.
        user = get_user_by_email(email)  # Función hipotética que buscas en la BD

        if user:
            return jsonify({"message": "Login successful", "user": user})
        else:
            # Registrar al nuevo usuario
            new_user = register_new_user(email, first_name, last_name, google_id)
            return jsonify({"message": "User registered successfully", "user": new_user})

    except ValueError:
        # Si el token no es válido, devuelve un error
        return jsonify({"error": "Invalid token"}), 400


def get_user_by_email(email):
    # Aquí deberías implementar la lógica para buscar al usuario por su email en tu BD
    return None  # Simulando que no existe el usuario

def register_new_user(email, first_name, last_name, google_id):
    # Aquí debes implementar la lógica para registrar al nuevo usuario en tu base de datos
    return {"email": email, "name": f"{first_name} {last_name}", "google_id": google_id}
    
    
    # --------------------------------------------------------------------------------------------------------
    
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
    
    
