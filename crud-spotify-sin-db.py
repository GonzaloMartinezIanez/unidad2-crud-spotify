import os, requests
from dotenv import load_dotenv
from flask import Flask, request
from pydantic import BaseModel, ValidationError
# pip install Flask, requests, python-dotenv, pydantic

spotify_token = 'Bearer BQBF6AKMN9XgDsp6SRcjTqNpWY3TpReP1v5_q_ws6MWedXKzfksz_xc8yj_YS6w7bs4WLYZFdOXhCbB57O9z5Ipk8VCSmMR4NTPTDAEVHZYIA5XZXAR70W39X9Dy9Lg-HF5onhxkKk4'

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


usersDB = [
    {
        'name': 'Gonzalo',
        'artists': ['Destripando la historia', 'Skillet'],
        'songs': ['Zeus', 'Ares']
    }  
]
class User(BaseModel):
    name: str  
    artists: list[str] 
    songs: list[str]


app = Flask(__name__)

def comprobar_usuario(username):
    for user in usersDB:
        if user['name'] == username:
            return user
    return None

# Users
@app.route('/users', methods=['GET'])
def get_usuer():
    return { 'usuarios': usersDB }, 200

@app.route('/users/<username>', methods=['GET'])
def get_one_usuer(username):
    user = comprobar_usuario(username)
    if user:
        return { 'usuario': user }, 200

    return { 'error': 'El usuario no está registrado en el sistema.' }, 404

@app.route('/users', methods=['POST'])
def post_users():
    new_users = request.get_json()['users']
    if 'users' not in new_users:
        return { 'error': 'Debes mandar una lista de usuarios.' }, 400
    
    for user in new_users:
        try:
            User(**user)
            usersDB.extend([user])            
        except ValidationError as e:
            return { 'error': e.errors() }, 404    
    return { 'message': 'Usuarios insertados correctamente.' }, 201
    
@app.route('/users/<username>', methods=['PUT'])
def put_users(username):
    new_user = request.get_json()
    try:
        User(**new_user)
    except ValidationError as e:
        return { 'error': e.errors() }, 400

    user = comprobar_usuario(username)
    if user:
        user['name'] = new_user['name']
        user['artists'] = new_user['artists']
        user['songs'] = new_user['songs']
        return { 'message': 'El usuario se ha modificado correctamente.' }, 200
    
    return { 'error': 'No se ha encontrado ningún usuario con el nombre de usuario proporcionado.' }, 404

@app.route('/users/<username>', methods=['DELETE'])
def delete_users(username):
    user = comprobar_usuario(username)
    if user:
        usersDB.remove(user)
        return { 'message': 'El usuario se ha eliminado correctamente.' }, 200
    
    return { 'message': 'No se ha encontrado ningún usuario con el nombre de usuario proporcionado.' }, 404

# Artists
@app.route('/artists/<username>', methods=['GET'])
def get_artists(username):
    user = comprobar_usuario(username)
    if user:
        if spotify_token == '':
            load_spotify_api()
        if user['artists'] == []:
            return { 'message': 'Este usuario no tiene artistas.' }, 404
        
        artists_id = []
        for artist in user['artists']:
            new_id = get_artist_or_song_id(artist, isArtist=True)
            artists_id.append(new_id)
        
        artists_info = []
        for id in artists_id:
            artist_data = get_artist(id)
            artists_info.append(artist_data)

        return { 'artists_info': artists_info }, 200

    return { 'message': 'No se ha encontrado ningún usuario con el nombre de usuario proporcionado.' }, 404

@app.route('/artists/<username>', methods=['POST'])
def post_artists(username):
    user = comprobar_usuario(username)
    if user:
        new_artists = request.get_json()['artists']
        if new_artists is not []:
            for artist in new_artists:
                user['artists'].extend([artist])    
            return { 'message': 'Artistas insertados correctamente.' }, 201
        else:
            return { 'error': 'Debes mandar los nuevos artistas del usuario' }, 400  

    return { 'error': 'El usuario no está registrado en el sistema.' }, 404

@app.route('/artists/<username>', methods=['PUT'])
def update_artists(username):
    user = comprobar_usuario(username)
    if user:
        new_artists = request.get_json()['artists']
        if new_artists is not []:
            user['artists'] = new_artists
            return { 'message': 'Artistas actualizados correctamente.' }, 201
    else:
        return { 'error': 'El usuario no está registrado en el sistema.' }, 404

@app.route('/artists/<username>', methods=['DELETE'])
def delete_artists(username):
    user = comprobar_usuario(username)
    if user:
        artists_to_delete = request.get_json()['artists']
        if artists_to_delete is not []:
            for artist in artists_to_delete:
                if artist in user['artists']:
                    user['artists'].remove(artist)
        return { 'message': 'Los artistas se han eliminado correctamente.' }, 200
    else:
        return { 'message': 'No se ha encontrado ningún usuario con el nombre de usuario proporcionado.' }, 404

# Songs
@app.route('/songs/<username>', methods=['GET'])
def get_songs(username):
    user = comprobar_usuario(username)
    if user:
        if spotify_token == '':
            load_spotify_api()
        if user['songs'] == []:
            return { 'message': 'Este usuario no tiene canciones.' }, 404
        
        songs_id = []
        for song in user['songs']:
            new_id = get_artist_or_song_id(song, isArtist=False)
            songs_id.append(new_id)
        
        songs_info = []
        for id in songs_id:
            song_data = get_song(id)
            songs_info.append(song_data)

        return { 'songs_info': songs_info }, 200

    return {
        'message': 'No se ha encontrado ningún usuario con el nombre de usuario proporcionado.'
    }, 404

@app.route('/songs/<username>', methods=['POST'])
def post_songs(username):
    user = comprobar_usuario(username)
    if user:
        new_songs = request.get_json()['songs']
        if new_songs is not []:
            for song in new_songs:
                user['songs'].extend([song])
  
            return { 'message': 'Canciones insertados correctamente.' }, 201
    else:
        return { 'error': 'El usuario no está registrado en el sistema.' }, 404

@app.route('/songs/<username>', methods=['PUT'])
def update_songs(username):
    user = comprobar_usuario(username)
    if user:
        new_songs = request.get_json()['songs']
        if new_songs is not []:
            user['songs'] = new_songs
            return { 'message': 'Canciones actualizadas correctamente.' }, 201
    else:
        return { 'error': 'El usuario no está registrado en el sistema.' }, 404

@app.route('/songs/<username>', methods=['DELETE'])
def delete_songs(username):
    user = comprobar_usuario(username)
    if user:
        songs_to_delete = request.get_json()['songs']
        if songs_to_delete is not []:
            for song in songs_to_delete:
                if song in user['songs']:
                    user['songs'].remove(song)
        return { 'message': 'Las canciones se han eliminado correctamente.' }, 200
    else:
        return { 'message': 'No se ha encontrado ningún usuario con el nombre de usuario proporcionado.' }, 404

if __name__ == '__main__':
    app.run(debug=True)