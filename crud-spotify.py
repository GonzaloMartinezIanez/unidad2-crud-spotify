import os, requests, json, sqlite3
from dotenv import load_dotenv
from flask import Flask, request, jsonify, abort
from pydantic import BaseModel, ValidationError
from flasgger import Swagger
# pip install Flask requests python-dotenv pydantic flasgger

# Alacena el token para usar la API de spotify
spotify_token = ""

# Obtiene el token para poder usar la API de spotify
# Hay que refrescar el token cada hora
def load_spotify_api():
    load_dotenv()
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    endpoint_access = "https://accounts.spotify.com/api/token"

    datos = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }

    get_token = requests.post(endpoint_access, headers={"Content-Type": "application/x-www-form-urlencoded"}, data=datos)
    global spotify_token
    # Para que funcionen las peticiones el token debe tener la palabra "Bearer" delante
    spotify_token = "Bearer " + get_token.json()["access_token"]

# Solicita el id de un artista o una cancion mediante su nombre
# Solo capta la primera opcion que aparece, por tanto cuanto mas especifico
# sea el nombre de la cancion mejor
def get_artist_or_song_id(name: str, isArtist: bool):
    # Sustituir los espacios de las canciones o artistas para poder mandarlos por url
    formated_name = name.replace(" ", "+")
    type = "artist" if isArtist else "track"
    endpoint = "https://api.spotify.com/v1/search?q=" + formated_name + "&type=" + type
    response = requests.get(endpoint, headers={"Authorization": spotify_token})

    # Si el token ha caducado hay que solicitar otro
    if(response.status_code != 200):
        load_spotify_api()
        response = requests.get(endpoint, headers={"Authorization": spotify_token})
    
    type = type + "s" # El atributo esta en plural
    id = response.json()[type]["items"][0]["id"]
    return id

# Devuelve informacion sobre los artistas a partir de su id
def get_artist(id: str):
    endpoint = "https://api.spotify.com/v1/artists/" + id
    response = requests.get(endpoint, headers={"Authorization": spotify_token})

    # Si el token ha caducado hay que solicitar otro
    if(response.status_code != 200):
        load_spotify_api()
        response = requests.get(endpoint, headers={"Authorization": spotify_token})
    
    data = response.json()
    artist_data = {
        "name": data["name"],
        "id": data["id"],
        "followers": data["followers"]["total"],
        "popularity": data["popularity"],
        "url": data["external_urls"]["spotify"]
    }
    return artist_data

# Devuelve informacion sobre las arcanciones a partir de su id
def get_song(id: str):
    endpoint = "https://api.spotify.com/v1/tracks/" + id
    response = requests.get(endpoint, headers={"Authorization": spotify_token})

    # Si el token ha caducado hay que solicitar otro
    if(response.status_code != 200):
        load_spotify_api()
        response = requests.get(endpoint, headers={"Authorization": spotify_token})

    data = response.json()
    song_data = {
        "name": data["name"],
        "id": data["id"],
        "duration_ms": data["duration_ms"],
        "popularity": data["popularity"],
        "url": data["external_urls"]["spotify"],
        "album": {
            "album_type": data["album"]["album_type"],
            "total_tracks": data["album"]["total_tracks"],
            "id": data["album"]["id"],
            "release_data": data["album"]["release_date"],
            "name": data["album"]["name"],
            "url": data["album"]["external_urls"]["spotify"]
        },
        "artist": {
            "name": data["artists"][0]["name"],
            "id": data["artists"][0]["id"],
            "url": data["artists"][0]["external_urls"]["spotify"]
        }
    }

    return song_data

# Modelo para validar los datos que se reciben en el body
class User(BaseModel):
    name: str
    artists: list[str]
    songs: list[str]

# La base de datos se guarda en la carpeta raiz del proyecto con este nombre
DB_PATH = "database.db"

# Se conecta con la base de datos y devuelve un objeto sobre el que hacer consultas
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Crea la base de datos si no existe
def initialize_database():
    conn = get_db()

    # Crea las trablas
    with open("database_tables.sql") as f:
        conn.executescript(f.read())
        conn.commit()
    
    conn.close()

initialize_database()

# Devuelve un objeto en formato json a partir de una tupla de la base de datos
# Esto hace mas facil manejar la informacion
def row_to_user(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "artists": json.loads(row["artists"]),
        "songs": json.loads(row["songs"])
    }

# Se crea la aplicacion
app = Flask(__name__)
# Se añade la documentacion
swagger = Swagger(app, template=json.load(open("swagger.json")))

# Users
# Obtiene todos los usuarios
@app.route("/users", methods=["GET"])
def get_usuarios():  
    conn = get_db()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()

    return jsonify({"usuarios": [row_to_user(r) for r in rows]}), 200

# Obtiene la informacion de un usuario mediante su nombre
@app.route("/users/<username>", methods=["GET"])
def get_user(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE name=?", (username,)).fetchone()
    conn.close()

    # Si existe se devuelve sus datos
    if row:
        return jsonify({"usuario": row_to_user(row)}), 200
    
    abort(404)

# Inserta uno o varios usuarios
@app.route("/users", methods=["POST"])
def post_usuarios():
    new_users = request.get_json()
    # Bad request
    if "users" not in new_users:
        abort(400)

    conn = get_db()
    for user in new_users["users"]:
        try:
            # Comprobar que el cuerpo tiene el formato correcto
            new_user = User(**user)
            conn.execute("INSERT OR IGNORE INTO users (name, artists, songs) VALUES (?, ?, ?)",
                (new_user.name, json.dumps(new_user.artists), json.dumps(new_user.songs))
            )
        except ValidationError as e:
            abort(404)
    conn.commit()
    conn.close()

    return jsonify({"message": "Usuarios insertados correctamente."}), 201

# Actualiza los datos de un usuario
@app.route("/users/<username>", methods=["PUT"])
def update_user(username):
    new_user = request.get_json()
    # Comprobar que el cuerpo tiene el formato correcto
    try:
        user = User(**new_user)
    except ValidationError as e:
        abort(400)

    conn = get_db()
    result = conn.execute("UPDATE users SET name=?, artists=?, songs=? WHERE name=?",
        (user.name, json.dumps(user.artists), json.dumps(user.songs), username)
    )

    conn.commit()
    conn.close()

    if result.rowcount:
        return jsonify({"message": "El usuario se ha modificado correctamente."}), 200
    
    abort(404)

# Elimina un usuario mediante su nombre
@app.route("/users/<username>", methods=["DELETE"])
def delete_user(username):
    conn = get_db()
    result = conn.execute("DELETE FROM users WHERE name=?", (username,))
    conn.commit()
    conn.close()

    # Si result.rowcount no existe quiere decir que no existe el usuario con este username
    if result.rowcount:
        return jsonify({"message": "El usuario se ha eliminado correctamente."}), 200
    
    abort(404)

# Artists
# Obtiene informacion de los artistas del usuario haciendo uso de la api de spotify
@app.route("/artists/<username>", methods=["GET"])
def get_artists(username):
    conn = get_db()
    row = conn.execute("SELECT artists FROM users WHERE name=?", (username,)).fetchone()
    conn.close()

    # No existe un usuario con este username
    if not row:
        conn.close()
        abort(404)
    
    # Primero se cargan los id de los artistas
    artists_id = []
    for artist in json.loads(row["artists"]):
        new_id = get_artist_or_song_id(artist, isArtist=True)
        artists_id.append(new_id)
    
    # Con los id de los artistas se obtiene su informacion
    artists_info = []
    for id in artists_id:
        artist_data = get_artist(id)
        artists_info.append(artist_data)
    
    return jsonify({"artists_info": artists_info}), 200

# Añade nuevos artistas al usuario seleccionado
@app.route("/artists/<username>", methods=["POST"])
def post_artists(username):
    new_artists = request.get_json()
    # Bad request
    if "artists" not in new_artists:
        abort(400)

    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE name=?", (username,)).fetchone()
    # No existe 
    if not row:
        conn.close()
        abort(404)

    # Se crea el json con los nuevos y antiguos artistas
    artists = json.loads(row["artists"])
    for artist in new_artists["artists"]:
        artists.append(artist)

    conn.execute("UPDATE users SET artists=? WHERE name=?", (json.dumps(artists), username))
    conn.commit()
    conn.close()

    return jsonify({"message": "Artistas insertados correctamente."}), 201

# Sustituye la lista de los artistas del usuario por una nueva proporcionada
@app.route("/artists/<username>", methods=["PUT"])
def update_artists(username):
    artists = request.get_json()
    # Bad request
    if "artists" not in artists:
        abort(400)

    new_artists = artists["artists"]

    # Sobreescribe los artistas de usuario
    conn = get_db()
    result = conn.execute("UPDATE users SET artists=? WHERE name=?",
        (json.dumps(new_artists), username)
    )
    conn.commit()
    conn.close()

    # Existe el usuario con este username
    if result.rowcount:
        return jsonify({"message": "Artistas actualizados correctamente."}), 200
    
    abort(404)

# Elimina uno o una lista de los artistas de un usuario
@app.route("/artists/<username>", methods=["DELETE"])
def delete_artists(username):
    artists_data = request.get_json()
    # Bad request
    if "artists" not in artists_data:
        abort(400)

    artists_to_delete = artists_data["artists"]

    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE name=?", (username,)).fetchone()

    # No existe el usuario con username
    if not row:
        conn.close()
        abort(404)

    artists = json.loads(row["artists"])

    # Eliminar solo los que existan
    artists = [a for a in artists if a not in artists_to_delete]

    # Sobreescribir los nuevos artistas
    conn.execute("UPDATE users SET artists=? WHERE name=?",
                 (json.dumps(artists), username))
    conn.commit()
    conn.close()

    return jsonify({"message": "Artistas eliminados correctamente."}), 200

# Songs
# Obtiene informacion de las canciones del usuario haciendo uso de la api de spotify
@app.route("/songs/<username>", methods=["GET"])
def get_songs(username):
    conn = get_db()
    row = conn.execute("SELECT songs FROM users WHERE name=?", (username,)).fetchone()

    # No existe el usuario con este username
    if not row:
        conn.close()
        abort(404)
    
    # Buscar los id de las canciones del usuario
    songs_id = []
    for song in json.loads(row["songs"]):
        new_id = get_artist_or_song_id(song, isArtist=False)
        songs_id.append(new_id)
    
    # Buscar informacion de las canciones a partir del id
    songs_info = []
    for id in songs_id:
        song_data = get_song(id)
        songs_info.append(song_data)
    
    conn.close()

    return jsonify({"songs_info": songs_info}), 200

# Añade nuevas canciones al usuario seleccionado
@app.route("/songs/<username>", methods=["POST"])
def post_songs(username):
    new_songs = request.get_json()
    # Bad request
    if "songs" not in new_songs:
        abort(400)

    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE name=?", (username,)).fetchone()
    # No existe el usuario
    if not row:
        conn.close()
        abort(404)

    # Se crea el json con las nuevas y antiguas canciones
    songs = json.loads(row["songs"])
    for artist in new_songs["songs"]:
        songs.append(artist)

    conn.execute("UPDATE users SET songs=? WHERE name=?", (json.dumps(songs), username))
    conn.commit()
    conn.close()

    return jsonify({"message": "Canciones insertados correctamente."}), 201

# Sustituye la lista de las canciones del usuario por una nueva proporcionada
@app.route("/songs/<username>", methods=["PUT"])
def update_songs(username):
    songs = request.get_json()
    # Bad request
    if "songs" not in songs:
        abort(400)

    new_songs = songs["songs"]

    conn = get_db()
    result = conn.execute("UPDATE users SET songs=? WHERE name=?",
        (json.dumps(new_songs), username)
    )
    conn.commit()
    conn.close()

    # Existe el usuario con este username
    if result.rowcount:
        return jsonify({"message": "Canciones actualizadas correctamente."}), 200
    
    abort(404)

# Elimina una o una lista de las canciones de un usuario
@app.route("/songs/<username>", methods=["DELETE"])
def delete_songs(username):
    songs_data = request.get_json()
    # Bad request
    if "songs" not in songs_data:
        abort(400)

    songs_to_delete = songs_data["songs"]

    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE name=?", (username,)).fetchone()

    # No existe el usuario con este username
    if not row:
        conn.close()
        abort(404)

    songs = json.loads(row["songs"])

    # Eliminar solo las que existan
    songs = [s for s in songs if s not in songs_to_delete]

    conn.execute("UPDATE users SET songs=? WHERE name=?",
                 (json.dumps(songs), username))
    conn.commit()
    conn.close()

    return jsonify({"message": "Canciones eliminadas correctamente."}), 200

# Devolver el error 400 a cualquier ruta que no este definida
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    return abort(400)

# Maneja los errores 400,
@app.errorhandler(400)
def resource_not_found(e):
    return jsonify({"error": "Bad requests. Para ver la documentación completa: http://127.0.0.1:5000/apidocs/"}), 400

# Maneja los errores 404, como solo se busca mediante el nombre de usuario
# el error hace referencia a los usuario, si hubiera mas tipos de busquedas
# habria que parametrizar esta funcion
@app.errorhandler(404)
def resource_not_found(e):
    return jsonify({"error": "Not found. El usuario no está registrado en el sistema."}), 404

# Maneja los errores 500
@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error. El servidor ha encontrado una situación que no sabe cómo manejarla."}), 500

# Lanzar la aplicacion
if __name__ == "__main__":
    app.run(debug=True)
