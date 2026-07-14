import os

from aiohttp import web

# Sur la plupart des panneaux Pterodactyl, le port interne à écouter est fourni
# via une variable d'environnement (souvent nommée SERVER_PORT ou PORT).
# On essaie plusieurs noms courants, avec 4137 (le port externe que tu m'as donné)
# comme dernier recours si aucune variable d'environnement n'est trouvée.
PORT = int(
    os.getenv("SERVER_PORT")
    or os.getenv("PORT")
    or os.getenv("APP_PORT")
    or 4137
)


async def handle_root(request: web.Request) -> web.Response:
    return web.Response(
        text=(
            "OK - le serveur de test répond correctement.\n"
            f"Port interne utilisé : {PORT}\n"
        )
    )


app = web.Application()
app.router.add_get("/", handle_root)

if __name__ == "__main__":
    print(f"Démarrage du serveur de test sur le port {PORT} ...")
    web.run_app(app, host="0.0.0.0", port=PORT)
