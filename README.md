# CRUD con spotify
Universidad Europea - Fundamendos de backend con python - Ejercicio entregable de la Unidad 2
Gonzalo Martínez Iáñez

## Instalación
Crear el entorno virtual
```
py -m venv venv
```
Activar el entorno (Windows, para linux o mac usar su forma para ejecutar programas)
```
.\venv\Scripts\activate
```
Instalar la librerias necesarias
```
pip install Flask, requests, python-dotenv, pydantic, flasgger
```
Crear el fichero .env con las claves correspondientes para hacer peticiones a la API de Spotify.
Para conseguir estas claves hay que registrarse en la [página web de desarrolladores de spotify](https://developer.spotify.com) y crear un proyecto que haga uso de API Web.
```
CLIENT_ID = 'clave_con_cliend_id'
CLIENT_SECRET = 'clave_con_secret_id'
```

## Ejecución
Lanzar la API y dejar ejecutando para poder recibir peticiones http (la ruta será http://127.0.0.1:5000)
```
py .\crud-spotify.py
```

## Memoria
### Funcionamiento

1. Users
    - GET /users : Devuelve todos los usuarios con sus canciones y artistas
    - GEt /users/<username> : Devuelve el nombre, canciones y artista del usuario con nombre username
    - POST /users : Añade un usuario o una lista de usuarios con nombre, canciones y artistas. Las canciones y artistas pueden estar vacios, pero debe estar el atributo en el json que se envía. Además no puede existir otro usuario con el mismo nombre.
    - PUT /users/<username> : Sustituye todos los atributos del usuario con nombre username.
    - DELETE /users/<username> : Elimina toda la información del usuario con nombre username.

2. Songs
    - GET /songs/<username> : Devuelve un listado con información sobre las canciones del usuario con nombre username.
    - POST /songs/<username> : Añade una o una lista de canciones al usuario con nombre username.
    - PUT /songs/<username> : Sustituye todas las canciones del usuario con nombre username por las nuevas proporcionadas.
    - DELETE /songs/<username> : Recibe una lista de canciones que eliminará del usuario con nombre username. Si el usuario no tiene esa canción no hará nada.

3. Artists
    - GET /artists/<username> : Devuelve un listado con información sobre los artistas del usuario con nombre username.
    - POST /artists/<username> : Añade una o una lista de artistas al usuario con nombre username.
    - PUT /artists/<username> : Sustituye todos los artistas del usuario con nombre username por las nuevas proporcionadas.
    - DELETE /artists/<username> : Recibe una lista de artistas que eliminará del usuario con nombre username. Si el usuario no tiene ese artista no hará nada.

4. Documentación
    - GET /apidocs

### API de spotify
Esta api tiene dos funciones que hacen uso de la API de spotify donde piden información sobre los artistas y las canciones de un usuario del sistema. Para ello, primero tienen que hacer una consulta para buscar el id que tienen las canciones o los artistas ya que en la base de datos solo se almacena el nombre. Una vez consultado el id, se vuelve a realizar otra petición donde se solicitan los datos que he considerado más relevantes.
Para los artistas:
- id
- nombre
- seguidores
- popularidad
- url a su página de spotify
Para las canciones:
- id
- nombre
- duración en milisegundos
- popularidad
- url a su página de spotify
- artistas:
    - id
    - nombre
    - fecha de lanzamiento
    - tipo de album
    - cuantas canciones tiene el album
    - url a su página de spotify
Para hacer uso de esta API hay que solicitar un token que solo tiene una vida de una hora. Por tanto hay que comprobar que el token es válido, de lo contrario se obtiene uno nuevo y se repite la primera petición.

### Conclusión
He aprendido a usar flask
Manejo de errores
Decisión de /users/<username> frente a /users?username=ejemplo
Versión inicial sin base de datos
Versión final con base de datos
Por qué usar sqlite, si se escala
Documentación automática con flasgger, la estructura del fichero swagger.json generado mediante ia.