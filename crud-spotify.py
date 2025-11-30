import os, requests, json, sqlite3
from dotenv import load_dotenv
from flask import Flask, request, jsonify, abort
from pydantic import BaseModel, ValidationError
from flasgger import Swagger
# pip install Flask requests python-dotenv pydantic flasgger

spotify_token = ''

def load_spotify_api():
    load_dotenv()
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    endpoint_access = 'https://accounts.spotify.com/api/token'

    datos = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }

    get_token = requests.post(endpoint_access, headers={'Content-Type': 'application/x-www-form-urlencoded'}, data=datos)
    global spotify_token
    spotify_token = 'Bearer ' + get_token.json()['access_token']

def get_artist_or_song_id(name: str, isArtist: bool):
    formated_name = name.replace(' ', '+')
    type = 'artist' if isArtist else 'track'
    endpoint = 'https://api.spotify.com/v1/search?q=' + formated_name + '&type=' + type
    response = requests.get(endpoint, headers={'Authorization': spotify_token})

    if(response.status_code != 200):
        load_spotify_api()
        response = requests.get(endpoint, headers={'Authorization': spotify_token})
    
    type = type + 's' # El atributo esta en plural
    id = response.json()[type]['items'][0]['id']
    return id

def get_artist(id: str):
    endpoint = 'https://api.spotify.com/v1/artists/' + id
    response = requests.get(endpoint, headers={'Authorization': spotify_token})

    if(response.status_code != 200):
        load_spotify_api()
        response = requests.get(endpoint, headers={'Authorization': spotify_token})
    
    data = response.json()
    artist_data = {
        'name': data['name'],
        'id': data['id'],
        'followers': data['followers']['total'],
        'popularity': data['popularity'],
        'url': data['external_urls']['spotify']
    }
    return artist_data


def get_song(id: str):
    endpoint = 'https://api.spotify.com/v1/tracks/' + id
    response = requests.get(endpoint, headers={'Authorization': spotify_token})

    if(response.status_code != 200):
        load_spotify_api()
        response = requests.get(endpoint, headers={'Authorization': spotify_token})

    data = response.json()
    song_data = {
        'name': data['name'],
        'id': data['id'],
        'duration_ms': data['duration_ms'],
        'popularity': data['popularity'],
        'url': data['external_urls']['spotify'],
        'album': {
            'album_type': data['album']['album_type'],
            'total_tracks': data['album']['total_tracks'],
            'id': data['album']['id'],
            'release_data': data['album']['release_date'],
            'name': data['album']['name'],
            'url': data['album']['external_urls']['spotify']
        },
        'artist': {
            'name': data['artists'][0]['name'],
            'id': data['artists'][0]['id'],
            'url': data['artists'][0]['external_urls']['spotify']
        }
    }

    return song_data

class User(BaseModel):
    name: str
    artists: list[str]
    songs: list[str]

DB_PATH = 'database.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    conn = get_db()

    with open('database_tables.sql') as f:
            conn.executescript(f.read())

    conn.commit()
    conn.close()

initialize_database()

def row_to_user(row):
    return {
        'id': row['id'],
        'name': row['name'],
        'artists': json.loads(row['artists']),
        'songs': json.loads(row['songs'])
    }

app = Flask(__name__)
swagger = Swagger(app, template=json.load(open("swagger.json")))

# Users
@app.route('/users', methods=['GET'])
def get_usuarios():  
    conn = get_db()
    rows = conn.execute('SELECT * FROM users').fetchall()
    conn.close()

    return jsonify({'usuarios': [row_to_user(r) for r in rows]}), 200

@app.route('/users/<username>', methods=['GET'])
def get_user(username):
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE name=?', (username,)).fetchone()
    conn.close()

    if row:
        return jsonify({'usuario': row_to_user(row)}), 200
    
    abort(404)

@app.route('/users', methods=['POST'])
def post_usuarios():
    new_users = request.get_json()
    if 'users' not in new_users:
        abort(400)

    conn = get_db()
    for user in new_users['users']:
        try:
            new_user = User(**user)
            conn.execute('INSERT OR IGNORE INTO users (name, artists, songs) VALUES (?, ?, ?)',
                (new_user.name, json.dumps(new_user.artists), json.dumps(new_user.songs))
            )
        except ValidationError as e:
            abort(404)
    conn.commit()
    conn.close()

    return jsonify({'message': 'Usuarios insertados correctamente.'}), 201

@app.route('/users/<username>', methods=['PUT'])
def update_user(username):
    new_user = request.get_json()
    try:
        user = User(**new_user)
    except ValidationError as e:
        abort(400)

    conn = get_db()
    result = conn.execute('UPDATE users SET name=?, artists=?, songs=? WHERE name=?',
        (user.name, json.dumps(user.artists), json.dumps(user.songs), username)
    )

    conn.commit()
    conn.close()

    if result.rowcount:
        return jsonify({'message': 'El usuario se ha modificado correctamente.'}), 200
    
    abort(404)

@app.route('/users/<username>', methods=['DELETE'])
def delete_user(username):
    conn = get_db()
    result = conn.execute('DELETE FROM users WHERE name=?', (username,))
    conn.commit()
    conn.close()

    if result.rowcount:
        return jsonify({'message': 'El usuario se ha eliminado correctamente.'}), 200
    
    abort(404)

# Artists
@app.route('/artists/<username>', methods=['GET'])
def get_artists(username):
    conn = get_db()
    row = conn.execute('SELECT artists FROM users WHERE name=?', (username,)).fetchone()
    conn.close()

    if not row:
        abort(404)
    
    artists_id = []
    for artist in json.loads(row['artists']):
        new_id = get_artist_or_song_id(artist, isArtist=True)
        artists_id.append(new_id)
    
    artists_info = []
    for id in artists_id:
        artist_data = get_artist(id)
        artists_info.append(artist_data)
    
    return jsonify({'artists_info': artists_info}), 200

@app.route('/artists/<username>', methods=['POST'])
def post_artists(username):
    new_artists = request.get_json()
    if 'artists' not in new_artists:
        abort(400)

    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE name=?', (username,)).fetchone()
    if not row:
        conn.close()
        abort(404)

    artists = json.loads(row['artists'])
    for artist in new_artists['artists']:
        artists.append(artist)

    conn.execute('UPDATE users SET artists=? WHERE name=?', (json.dumps(artists), username))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Artistas insertados correctamente.'}), 201

@app.route('/artists/<username>', methods=['PUT'])
def update_artists(username):
    artists = request.get_json()
    if 'artists' not in artists:
        abort(400)

    new_artists = artists['artists']

    conn = get_db()
    result = conn.execute('UPDATE users SET artists=? WHERE name=?',
        (json.dumps(new_artists), username)
    )
    conn.commit()
    conn.close()

    if result.rowcount:
        return jsonify({'message': 'Artistas actualizados correctamente.'}), 200
    
    abort(404)

@app.route('/artists/<username>', methods=['DELETE'])
def delete_artists(username):
    artists_data = request.get_json()
    if 'artists' not in artists_data:
        abort(400)

    artists_to_delete = artists_data['artists']

    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE name=?', (username,)).fetchone()

    if not row:
        conn.close()
        abort(404)

    artists = json.loads(row['artists'])

    # Eliminar solo los que existan
    artists = [a for a in artists if a not in artists_to_delete]

    conn.execute('UPDATE users SET artists=? WHERE name=?',
                 (json.dumps(artists), username))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Artistas eliminados correctamente.'}), 200

# Songs
@app.route('/songs/<username>', methods=['GET'])
def get_songs(username):
    conn = get_db()
    row = conn.execute('SELECT songs FROM users WHERE name=?', (username,)).fetchone()

    if not row:
        conn.close()
        abort(404)
    
    songs_id = []
    for song in json.loads(row['songs']):
        new_id = get_artist_or_song_id(song, isArtist=False)
        songs_id.append(new_id)
    
    songs_info = []
    for id in songs_id:
        song_data = get_song(id)
        songs_info.append(song_data)
    
    conn.close()

    return jsonify({'songs_info': songs_info}), 200

@app.route('/songs/<username>', methods=['POST'])
def post_songs(username):
    new_songs = request.get_json()
    if 'songs' not in new_songs:
        abort(400)

    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE name=?', (username,)).fetchone()
    if not row:
        conn.close()
        abort(404)

    songs = json.loads(row['songs'])
    for artist in new_songs['songs']:
        songs.append(artist)

    conn.execute('UPDATE users SET songs=? WHERE name=?', (json.dumps(songs), username))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Canciones insertados correctamente.'}), 201

@app.route('/songs/<username>', methods=['PUT'])
def update_songs(username):
    songs = request.get_json()
    if 'songs' not in songs:
        abort(400)

    new_songs = songs['songs']

    conn = get_db()
    result = conn.execute('UPDATE users SET songs=? WHERE name=?',
        (json.dumps(new_songs), username)
    )
    conn.commit()
    conn.close()

    if result.rowcount:
        return jsonify({'message': 'Canciones actualizadas correctamente.'}), 200
    
    abort(404)

@app.route('/songs/<username>', methods=['DELETE'])
def delete_songs(username):
    songs_data = request.get_json()
    if 'songs' not in songs_data:
        abort(400)

    songs_to_delete = songs_data['songs']

    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE name=?', (username,)).fetchone()

    if not row:
        conn.close()
        abort(404)

    songs = json.loads(row['songs'])

    # Eliminar solo los que existan
    songs = [s for s in songs if s not in songs_to_delete]

    conn.execute('UPDATE users SET songs=? WHERE name=?',
                 (json.dumps(songs), username))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Canciones eliminadas correctamente.'}), 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return abort(400)

@app.errorhandler(400)
def resource_not_found(e):
    return jsonify({'error': 'Bad requests. Para ver la documentación completa: http://127.0.0.1:5000/apidocs/'}), 400

@app.errorhandler(404)
def resource_not_found(e):
    return jsonify({'error': 'Not found. El usuario no está registrado en el sistema.'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error. El servidor ha encontrado una situación que no sabe cómo manejarla.'}), 500

if __name__ == '__main__':
    app.run(debug=True)
