
import os
import tekore as tk
import pickle
import requests
import io
import webbrowser
import time
from t_modules.t_extra import Timer
import urllib.request


class SpotCtl:

    def __init__(self, tauon):
        self.tauon = tauon

        self.start_timer = Timer()
        self.status = 0
        self.spotify = None
        self.loaded_art = ""
        self.playing = False
        self.coasting = False
        self.paused = False
        self.token = None
        self.cred = None
        self.redirect_uri = f"http://localhost:7811/spotredir"
        self.current_imports = {}

        self.progress_timer = Timer()
        self.update_timer = Timer()

        self.token_path = os.path.join(self.tauon.user_directory, "spot-r-token")

    def prep_cred(self):
        self.cred = tk.auth.RefreshingCredentials(client_id=self.tauon.prefs.spot_client,
                                    client_secret=self.tauon.prefs.spot_secret,
                                    redirect_uri=self.redirect_uri)

    def connect(self):
        if self.cred is None:
            self.prep_cred()
        if self.spotify is None:
            if self.token is None:
                self.load_token()
            if self.token:
                print("Init spotify support")
                self.spotify = tk.Spotify(self.token)

    def paste_code(self, code):
        if self.cred is None:
            self.prep_cred()
        self.token = self.cred.request_user_token(code)
        if self.token:
            self.save_token()
            self.tauon.gui.show_message("Spotify account connected", mode="done")

    def save_token(self):
        if self.token:
            pickle.dump(self.token, open(self.token_path, "wb"))

    def delete_token(self):
        if os.path.isfile(self.token_path):
            os.remove(self.token_path)
        self.token = None

    def load_token(self):
        if os.path.isfile(self.token_path):
            f = open(self.token_path, "rb")
            self.token = pickle.load(f)
            f.close()
            print("Loaded spotify token from file")


    def auth(self):
        if self.cred is None:
            self.prep_cred()
        url = self.cred.user_authorisation_url(scope="user-read-playback-position streaming user-modify-playback-state user-library-modify user-library-read user-read-currently-playing user-read-playback-state")
        webbrowser.open(url, new=2, autoraise=True)

    def control(self, command, param=None):

        try:
            if command == "pause" and (self.playing or self.coasting) and not self.paused:
                self.spotify.playback_pause()
                self.paused = True
                self.start_timer.set()
            if command == "stop" and self.playing:
                self.spotify.playback_pause()
                self.paused = False
                self.playing = False
                self.coasting = False
                self.start_timer.set()
            if command == "resume" and (self.coasting or self.playing) and self.paused:
                self.spotify.playback_resume()
                self.paused = False
                self.start_timer.set()
            if command == "volume":
                self.spotify.playback_volume(param)
            if command == "seek":
                self.spotify.playback_seek(param)
                self.start_timer.set()
            if command == "next":
                self.spotify.playback_next(param)
                #self.start_timer.set()
            if command == "previous":
                self.spotify.playback_previous(param)
                #self.start_timer.set()

        except Exception as e:
            print(repr(e))
            if "No active device found" in repr(e):
                self.tauon.gui.show_message("It looks like there are no more active Spotify devices")

    def get_album_url_from_local(self, track_object):

        if "spotify-album-url" in track_object.misc:
            return track_object.misc["spotify-album-url"]

        self.connect()
        if not self.spotify:
            return None

        results = self.spotify.search(track_object.artist + " " + track_object.album, types=('album',), limit=1)
        for album in results[0].items:
            return album.external_urls["spotify"]

        return None

    def get_playlists(self):
        self.connect()
        if not self.spotify:
            return None

        results = self.spotify.playlists(self.spotify.current_user().id)
        print(results)

    def search(self, text):
        self.connect()
        if not self.spotify:
            return
        results = self.spotify.search(text,
                                      types=('artist', 'album',),
                                      limit=20
                                      )
        finds = []


        self.tauon.QuickThumbnail.queue.clear()

        if results[0]:
            for album in results[0].items[0:1]:

                img = self.tauon.QuickThumbnail()
                img.url = album.images[-1].url
                img.size = round(50 * self.tauon.gui.scale)
                self.tauon.QuickThumbnail().items.append(img)
                self.tauon.QuickThumbnail().queue.append(img)
                try:
                    self.tauon.gall_ren.lock.release()
                except:
                    pass

                finds.append((11, (album.name, album.artists[0].name), album.external_urls["spotify"], 0, 0, img))

            for artist in results[1].items[0:1]:
                finds.insert(2, (10, artist.name, artist.external_urls["spotify"], 0, 0, None))

            for i, album in enumerate(results[0].items[1:]):

                img = self.tauon.QuickThumbnail()
                img.url = album.images[-1].url
                img.size = round(50 * self.tauon.gui.scale)
                self.tauon.QuickThumbnail().items.append(img)
                if i < 10:
                    self.tauon.QuickThumbnail().queue.append(img)
                try:
                    self.tauon.gall_ren.lock.release()
                except:
                    pass

                finds.append((11, (album.name, album.artists[0].name), album.external_urls["spotify"], 0, 0, img))

            # for artist in results[1].items[1:2]:
            #     finds.append((10, artist.name, artist.external_urls["spotify"], 0, 0, None))

            # for album in results[0].items[8:]:
            #     finds.append((11, (album.name, album.artists[0].name), album.external_urls["spotify"], 0, 0, None))

        return finds


    def search_track(self, track):
        if track is None:
            return

        self.connect()
        if not self.spotify:
            return

        if track.artist and track.title:
            results = self.spotify.search(track.artist + " " + track.title,
                                     types=('track',),
                                     limit=1
                                     )
            print(dir(results))
            print(results)

    def prime_device(self):
        self.connect()
        if not self.spotify:
            return

        devices = self.spotify.playback_devices()
        if not devices:
            webbrowser.open("https://open.spotify.com/", new=2, autoraise=False)
            tries = 0
            while not devices:
                time.sleep(2)
                if tries == 0:
                    self.tauon.focus_window()
                devices = self.spotify.playback_devices()
                tries += 1
                if tries > 4:
                    break
            if not devices:
                return False
        for d in devices:
            if d.is_active:
                return None
        for d in devices:
            if not d.is_restricted:
                return d.id
        return None

    def play_target(self, id):

        self.connect()
        if not self.spotify:
            return

        d_id = self.prime_device()
        if d_id is False:
            return

        #if self.tauon.pctl.playing_state == 1 and self.playing and self.tauon.pctl.playing_time
        #try:
        self.spotify.playback_start_tracks([id], device_id=d_id)
        # except Exception as e:
        #     self.tauon.gui.show_message("Error. Do you have playback started somewhere?", mode="error")
        self.playing = True
        self.progress_timer.set()
        self.start_timer.set()

    def get_library_albums(self):
        self.connect()
        if not self.spotify:
            return

        albums = self.spotify.saved_albums()

        playlist = []
        self.update_existing_import_list()

        for a in albums.items:
            self.load_album(a.album, playlist)

        self.tauon.pctl.multi_playlist.append(self.tauon.pl_gen(title="Spotify Albums", playlist=playlist))

    def append_album(self, url, playlist_number=None, return_list=False):

        self.connect()
        if not self.spotify:
            return

        id = url.strip("/").split("/")[-1]

        album = self.spotify.album(id)
        playlist = []
        self.update_existing_import_list()
        self.load_album(album, playlist)

        if return_list:
            return playlist

        if playlist_number is None:
            playlist_number = self.tauon.pctl.active_playlist_viewing

        self.tauon.pctl.multi_playlist[playlist_number][2].extend(playlist)
        self.tauon.gui.pl_update += 1

    def playlist(self, url):
        self.connect()
        if not self.spotify:
            return

        id = url.strip("/").split("/")[-1]
        p = self.spotify.playlist(id)
        playlist = []
        self.update_existing_import_list()

        for item in p.tracks.items:
            nt = self.load_track(item.track)
            self.tauon.pctl.master_library[nt.index] = nt
            playlist.append(nt.index)


        title = p.name + " by " + p.owner.display_name
        self.tauon.pctl.multi_playlist.append(self.tauon.pl_gen(title=title, playlist=playlist))
        self.tauon.switch_playlist(len(self.tauon.pctl.multi_playlist) - 1)

    def artist_playlist(self, url):
        id = url.strip("/").split("/")[-1]
        artist = self.spotify.artist(id)
        artist_albums = self.spotify.artist_albums(id, limit=30, include_groups=["album"])
        playlist = []
        self.update_existing_import_list()

        for a in artist_albums.items:
            full_album = self.spotify.album(a.id)
            self.load_album(full_album, playlist)

        self.tauon.pctl.multi_playlist.append(self.tauon.pl_gen(title="Spotify: " + artist.name, playlist=playlist))
        self.tauon.switch_playlist(len(self.tauon.pctl.multi_playlist) - 1)

    def update_existing_import_list(self):
        self.current_imports.clear()
        for tr in self.tauon.pctl.master_library.values():
            if "spotify-track-url" in tr.misc:
                self.current_imports[tr.misc["spotify-track-url"]] = tr

    def load_album(self, album, playlist):
        #a = item
        album_url = album.external_urls["spotify"]
        art_url = album.images[0].url
        album_name = album.name
        total_tracks = album.total_tracks
        date = album.release_date
        album_artist = album.artists[0].name
        id = album.id
        parent = (album_artist + " - " + album_name).strip("- ")

        # print(a.release_date, a.name)
        for track in album.tracks.items:

            pr = self.current_imports.get(track.external_urls["spotify"])
            if pr:
                new = False
                nt = pr
            else:
                new = True
                nt = self.tauon.TrackClass()
                nt.index = self.tauon.pctl.master_count

            nt.is_network = True
            nt.file_ext = "SPTY"
            nt.url_key = track.id
            nt.misc["spotify-artist-url"] = track.artists[0].external_urls["spotify"]
            nt.misc["spotify-album-url"] = album_url
            nt.misc["spotify-track-url"] = track.external_urls["spotify"]
            nt.artist = track.artists[0].name
            nt.album_artist = album_artist
            nt.date = date
            nt.album = album_name
            nt.disc_total = track.disc_number
            nt.length = track.duration_ms / 1000
            nt.title = track.name
            nt.track_number = track.track_number
            nt.track_total = total_tracks
            nt.art_url_key = art_url
            nt.parent_folder_path = parent
            nt.parent_folder_name = parent
            if new:
                self.tauon.pctl.master_count += 1
                self.tauon.pctl.master_library[nt.index] = nt
            playlist.append(nt.index)



    def load_track(self, track, update_master_count=True):

        pr = self.current_imports.get(track.external_urls["spotify"])
        if pr:
            new = False
            nt = pr
        else:
            new = True
            nt = self.tauon.TrackClass()
            nt.index = self.tauon.pctl.master_count

        nt.is_network = True
        nt.file_ext = "SPTY"
        nt.url_key = track.id
        if new:
            nt.misc["spotify-artist-url"] = track.artists[0].external_urls["spotify"]
            # nt.misc["spotify-album-url"] = album_url
            nt.misc["spotify-track-url"] = track.external_urls["spotify"]
        nt.artist = track.artists[0].name
        nt.album_artist = track.album.artists[0].name
        nt.date = track.album.release_date
        nt.album = track.album.name
        nt.disc_total = track.disc_number
        nt.length = track.duration_ms / 1000
        nt.title = track.name
        nt.track_number = track.track_number
        # nt.track_total = total_tracks
        nt.art_url_key = track.album.images[0].url
        parent = (nt.album_artist + " - " + nt.album).strip("- ")
        nt.parent_folder_path = parent
        nt.parent_folder_name = parent

        if update_master_count and new:
            self.tauon.pctl.master_count += 1

        return nt

    def like_track(self, tract_object):
        track_url = tract_object.misc.get("spotify-track-url", False)
        if track_url:
            id = track_url.strip("/").split("/")[-1]
            results = self.spotify.saved_tracks_contains([id])
            if not results or results[0] is False:
                self.spotify.saved_tracks_add([id])
                tract_object.misc["spotify-liked"] = True
                self.tauon.gui.show_message("Track added to liked tracks", mode="done")
                return
            self.tauon.gui.show_message("Track is already liked")
            return

    def unlike_track(self, tract_object):
        track_url = tract_object.misc.get("spotify-track-url", False)
        if track_url:
            id = track_url.strip("/").split("/")[-1]
            results = self.spotify.saved_tracks_contains([id])
            if not results or results[0] is True:
                self.spotify.saved_tracks_delete([id])
                tract_object.pop("spotify-liked", None)
                self.tauon.gui.show_message("Track removed from liked tracks", mode="done")
                return
            self.tauon.gui.show_message("Track was already un-liked")
            return

    def get_library_likes(self):
        self.connect()
        if not self.spotify:
            return

        self.update_existing_import_list()
        tracks = self.spotify.saved_tracks()

        playlist = []

        for tr in self.tauon.pctl.master_library.values():
            tr.misc.pop("spotify-liked", None)

        for item in tracks.items:
            nt = self.load_track(item.track)
            self.tauon.pctl.master_library[nt.index] = nt
            playlist.append(nt.index)
            nt.misc["spotify-liked"] = True

        for p in self.tauon.pctl.multi_playlist:
            if p[0] == "Spotify Likes":
                p[2][:] = playlist[:]
                return

        self.tauon.pctl.multi_playlist.append(self.tauon.pl_gen(title="Spotify Likes", playlist=playlist))


    def monitor(self):
        if self.playing and self.start_timer.get() > 5:
            result = self.spotify.playback_currently_playing()
            tr = self.tauon.pctl.playing_object()
            if result is None or tr is None:
                self.tauon.pctl.stop()
                return
            if result.item.name != tr.title:
                self.tauon.pctl.playing_state = 3
                self.playing = False
                self.coasting = True
                self.coast_update(result)
                self.tauon.gui.pl_update += 2
                return

            p = result.progress_ms
            if p is not None:
                self.tauon.pctl.playing_time = p / 1000
            self.tauon.pctl.decode_time = self.tauon.pctl.playing_time

    def update(self):

        if self.playing:
            self.coasting = False
            return

        self.connect()
        if not self.spotify:
            return

        result = self.spotify.playback_currently_playing()

        if result is None or result.is_playing is False:
            if self.coasting:
                self.tauon.pctl.stop()
                self.coasting = False
            else:
                self.tauon.gui.show_message("This Spotify account isn't currently playing anything")
            return

        self.coasting = True
        self.tauon.pctl.playing_state = 3

        if result.is_playing:
            self.paused = False
        else:
            self.paused = True

        self.coast_update(result)

    def append_playing(self, playlist_number):
        if not self.coasting:
            return
        tr = self.tauon.pctl.playing_object()
        if tr and "spotify-album-url" in tr.misc:
            self.append_album(tr.misc["spotify-album-url"], playlist_number)

    def coast_update(self, result):

        self.tauon.dummy_track.artist = result.item.artists[0].name
        self.tauon.dummy_track.title = result.item.name
        self.tauon.dummy_track.album = result.item.album.name
        self.tauon.dummy_track.file_ext = "Spotify"

        self.progress_timer.set()
        self.update_timer.set()

        d = result.item.duration_ms
        if d is not None:
            self.tauon.pctl.playing_length = d / 1000

        p = result.progress_ms
        if p is not None:
            self.tauon.pctl.playing_time = p / 1000

        self.tauon.pctl.decode_time = self.tauon.pctl.playing_time

        art_url = result.item.album.images[0].url
        self.tauon.dummy_track.url_key = result.item.id
        self.tauon.dummy_track.misc["spotify-album-url"] = result.item.album.external_urls["spotify"]
        self.tauon.dummy_track.misc["spotify-track-url"] = result.item.external_urls["spotify"]

        if art_url and self.loaded_art != art_url:
            self.loaded_art = art_url
            art_response = requests.get(art_url)
            if self.tauon.pctl.radio_image_bin:
                self.tauon.pctl.radio_image_bin.close()
                self.tauon.pctl.radio_image_bin = None
            self.tauon.pctl.radio_image_bin = io.BytesIO(art_response.content)
            self.tauon.pctl.radio_image_bin.seek(0)
            self.tauon.dummy_track.art_url_key = "ok"
            self.tauon.gui.clear_image_cache_next = True

        self.tauon.gui.update += 2
