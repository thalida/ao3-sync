from ao3_sync.api import AO3ApiClient

api = AO3ApiClient(
    username="jessikajones",
    password='!^}t#hQJ"5zU10:b3c\\9MM',
    debug=True,
    use_debug_cache=False,
    use_history=False,
)
# api.series.fetch_works("1492355")
api.series.sync("1492355")
