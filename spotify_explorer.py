import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from nicegui import ui, app
from spotipy.cache_handler import CacheHandler

app.on_exception(lambda e: ui.notify(e, type="warning"))


class NiceguiCache(CacheHandler):
    def get_cached_token(self):
        if "spotipy_token" in app.storage.user:
            print("Got token")
            return app.storage.user["spotipy_token"]
        else:
            print("No saved toke")
            return None

    def save_token_to_cache(self, token):
        print("Saving token", token)
        app.storage.user["spotipy_token"] = token

    @staticmethod
    def clear_cache():
        app.storage.user["spotipy_token"] = None


device_id = None


def artists_to_df(artists):
    arts = []
    for i in artists:
        try:
            img = i["images"][-1]["url"]
        except:
            img = ""
        art = {
            "img": '<img src="%s" width="30">' % img,
            "use": False,
            "artist": i["name"],
            "artistid": i["id"],
        }
        arts += [art]
    return arts


def tracks_to_df(tracks):
    trax = []
    for track in tracks:
        trx = {
            "img": '<img src="%s" width="30">' % track["album"]["images"][-1]["url"],
            "use": False,
            "track": track["name"],
            "trackid": track["id"],
            "artist": track["artists"][0]["name"],
            "artistid": track["artists"][0]["id"],
            "album": track["album"]["name"],
            "albumid": track["album"]["id"],
            "tracknum": track["track_number"],
            "releasedate": track["album"]["release_date"],
            "duration": track["duration_ms"] / 1000,
        }
        trax += [trx]
    return trax


@ui.page("/auth")
async def page(client):
    def logout():
        NiceguiCache.clear_cache()
        ui.open("/auth", new_tab=False)

    def onsearch(e):
        print(stsearch.value)
        ui.notify("Searching...")
        results = spotify.search(q=stsearch.value, type="track,artist", limit=30)
        track_grid.options["rowData"] = tracks_to_df(results["tracks"]["items"])
        artist_grid.options["rowData"] = artists_to_df(results["artists"]["items"])
        track_grid.update()
        artist_grid.update()

    async def do_rec(e):
        ui.notify("Getting recs...")
        rows = select_grid.options["rowData"]
        if rows:
            seed_tracks = []
            seed_artists = []
            for row in rows:
                if "trackid" in row:
                    seed_tracks += [row["trackid"]]
                elif "artistid" in row:
                    seed_artists += [row["artistid"]]
            reccs = spotify.recommendations(
                limit=100,
                seed_artists=seed_artists,
                seed_tracks=seed_tracks,
                seed_genre=None,
            )
            print(reccs["seeds"])
            rec_grid.options["rowData"] = tracks_to_df(reccs["tracks"])
            rec_grid.update()
        else:
            ui.notify("No rows selected.")

    def on_cell_click(ev):
        """On click of a rec, start playing, smart skip the intro"""
        row = ev.args["data"]
        ui.notify("Playing " + row["track"] + " / " + str(row["duration"]))
        print(row)
        dur = row["duration"]
        if dur < 60 * 3:
            start = 10
        if dur < 60 * 4.5:  # 270
            start = 30
        if dur < 60 * 7:  # 420
            start = 60
        else:
            start = 90
        spotify.start_playback(
            device_id=device_id,
            context_uri="spotify:album:" + row["albumid"],
            offset={"uri": "spotify:track:" + row["trackid"]},
            position_ms=start * 1000,
        )

    def on_result_click(ev):
        print(ev)
        row = ev.args["data"]
        select_grid.options["rowData"] += [row]
        select_grid.update()

    def on_sel_click(ev):
        select_grid.options["rowData"].pop(int(ev.args["rowId"]))
        select_grid.update()

    def jump(ev):
        """Fast forward playback 30 seconds"""
        res = spotify.current_playback()
        vol = res["device"]["volume_percent"]
        if vol != vol_slider.value:
            vol_slider.value = vol
        print(res)
        spotify.seek_track(res["progress_ms"] + 30000, device_id=device_id)

    def jumpback(ev):
        """Rewind playback 30 seconds"""
        res = spotify.current_playback()
        vol = res["device"]["volume_percent"]
        if vol != vol_slider.value:
            vol_slider.value = vol
        print(res)
        spotify.seek_track(res["progress_ms"] - 30000, device_id=device_id)

    def set_device(ev):
        device_id = ev.value
        spotify.transfer_playback(device_id)

    def get_devices():
        devs = spotify.devices()
        print(devs)
        devices = {}
        selected = None
        vol = 0
        devtypes = {
            "tv": "📺",
            "computer": "💻",
            "smartphone": "📱",
            "speaker": "🔊",
        }
        for dev in devs["devices"]:
            name = dev["name"]
            dtype = dev["type"].lower()
            if dtype in devtypes:
                name = devtypes[dtype] + name
            devices[dev["id"]] = name
            if dev["is_active"]:
                selected = dev["id"]
                vol = dev["volume_percent"]

        return devices, selected, vol

    async def do_auth():
        scope = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing,app-remote-control,streaming"
        sp_auth = SpotifyOAuth(
            scope=scope, cache_handler=NiceguiCache(), open_browser=False
        )
        token_info = sp_auth.get_cached_token()
        access_token = None
        # We have a cached token
        if token_info:
            access_token = token_info["access_token"]
        else:  # check if a token got passed in the URL
            await client.connected()
            url = await ui.run_javascript("window.location.href")
            print(url)
            code = sp_auth.parse_response_code(url)
            if code != url:
                token = sp_auth.get_access_token(code)
                access_token = token["access_token"]
                ui.open("/auth", new_tab=False)

        # No token, redirecto to spotify
        if not access_token:
            ui.button(
                "Authorize Spotify",
                on_click=lambda ev: ui.open(sp_auth.get_authorize_url(), new_tab=False),
            )
            return None

        return spotipy.Spotify(access_token)

    device_id = None
    print("Loading")

    spotify = await do_auth()
    if not spotify:
        print("Need auth")
        return

    me = spotify.me()
    print("Authed: ", me)

    print("Building UI")
    with ui.row():
        ui.label("Spotify Explorer")
        dark = ui.dark_mode()
        ui.label("Switch mode:")
        ui.button("Dark", on_click=dark.enable)
        ui.button("Light", on_click=dark.disable)
        ui.label("User: " + me["display_name"])
        ui.button("Logout", on_click=logout)

    stsearch = ui.input("Search keywords").on("keydown.enter", onsearch)
    ui.label("Search results: (click to add to seed list)")
    with ui.element("div").classes("w-full flex flex-wrap"):
        track_grid = (
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "", "field": "img", "maxWidth": 60},
                        {"headerName": "Artist", "field": "artist", "sortable": True},
                        {"headerName": "Track", "field": "track", "sortable": True},
                        {"headerName": "Album", "field": "album", "sortable": True},
                    ],
                    "rowData": [],
                    "rowSelection": "multiple",
                },
                html_columns=[0],
            )
            .on("cellClicked", on_result_click)
            .style("box-sizing: border-box; flex: 1 0 50%; min-width: 600px")
        )
        artist_grid = (
            ui.aggrid(
                {
                    "columnDefs": [
                        {
                            "headerName": "",
                            "field": "img",
                            "maxWidth": 60,
                            "sortable": True,
                        },
                        {"headerName": "Artist", "field": "artist", "sortable": True},
                    ],
                    "rowData": [],
                    "rowSelection": "multiple",
                },
                html_columns=[0],
            )
            .on("cellClicked", on_result_click)
            .style("box-sizing: border-box; flex: 1 0 50%; min-width: 500px")
        )

    ui.label("Seed tracks/aritsts: (click to remove)")
    select_grid = ui.aggrid(
        {
            "columnDefs": [
                {"headerName": "", "field": "img", "maxWidth": 60},
                {"headerName": "Artist", "field": "artist", "sortable": True},
                {"headerName": "Track", "field": "track", "sortable": True},
            ],
            "rowData": [],
            "rowSelection": "multiple",
        },
        html_columns=[0],
    ).on("cellClicked", on_sel_click)

    ui.button("Get Reccomendations", on_click=do_rec)
    ui.label("Recommendations: (click to play)")
    rec_grid = ui.aggrid(
        {
            "columnDefs": [
                {"headerName": "", "field": "img", "maxWidth": 60},
                {"headerName": "Track", "field": "track", "sortable": True},
                {"headerName": "Artist", "field": "artist", "sortable": True},
                {"headerName": "Album", "field": "album", "sortable": True},
                {"headerName": "Released", "field": "releasedate", "sortable": True},
            ],
            "rowData": [],
            "rowSelection": "multiple",
        },
        html_columns=[0],
    ).on("cellClicked", on_cell_click)

    with ui.row().classes("w-full no-wrap"):
        ui.button("<< RR", on_click=jumpback).style("min-width: max-content")
        ui.button("FF >>", on_click=jump).style("min-width: max-content")
        ui.button("||", on_click=lambda e: spotify.pause_playback(device_id=device_id))
        ui.button(">", on_click=lambda e: spotify.start_playback(device_id=device_id))

        devices, selected, vol = get_devices()
        ui.select(devices, label="Device", value=selected, on_change=set_device)
        vol_slider = (
            ui.slider(min=0, max=100, value=vol, step=1)
            .on(
                "update:model-value",
                lambda e: spotify.volume(e.args, device_id),
                throttle=1.0,
            )
            .classes("w-1/3")
        )


ui.link("Get started", page)
ui.run(
    favicon="ᯤ",
    dark=None,
    title="Spotify Explorer",
    storage_secret="this is a private key no hacking",
)
