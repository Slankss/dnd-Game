"""State-update yamasının dünyaya uygulanması (`deep_merge_world_state`).

Anlatıcının yanıtından sökülen yama buradan geçer. Kurallar davranış olarak
BİREBİR korunmalı — her biri geçmişte somut bir hatanın panzehiri:
boş zaman alanı mevcut değeri ezmez, tanımadık isim `npcs`'e düşer,
`inventory` üzerine yazmaz birleşir, `"+3"` göreli stok değişimidir.
"""

from .challenges import Challenge
from .factions import Faction
from .options import normalize_list
from .person import Person
from .text import as_int, canonical_name

# Dünya saati/takvimi/havası — state-update ile güncellenen, hepsi metin alan.
TIME_FIELDS = ("time_of_day", "clock", "season", "weather", "temperature")

TENSION_LEVELS = ("düşük", "orta", "yüksek")


class WorldPatchMixin:
    """`WorldState`'in yama tarafı. Tek başına kullanılmaz."""

    def merge_patch(self, patch: dict, vitals_touched: dict = None) -> None:
        """`vitals_touched` verilirse, anlatıcının bu turda elle yazdığı
        gösterge alanları {isim: {alan}} olarak oraya biriktirilir."""
        # Model gün sayısını bazen "98" diye string yazıyor; eskiden bu sessizce
        # yok sayılıp başlıktaki gün sayacı hiç ilerlemiyordu.
        day = patch.get("day")
        if isinstance(day, bool):
            day = None
        if isinstance(day, str) and day.strip().isdigit():
            day = int(day.strip())
        if isinstance(day, (int, float)):
            self._set("day", int(day))

        # Zaman ve hava: anlatıcı her turda ilerletir (saat akar, gün döner, hava
        # değişir). Boş string gönderilirse mevcut değer korunur — model alanı
        # "unutup" boş bıraktığında dünya saati sıfırlanmasın.
        for name in TIME_FIELDS:
            value = patch.get(name)
            if isinstance(value, str) and value.strip():
                self._set(name, value.strip())

        if "location" in patch and isinstance(patch["location"], str):
            self._set("location", patch["location"])

        if patch.get("tension") in TENSION_LEVELS:
            self._set("tension", patch["tension"])

        if "factions" in patch and isinstance(patch["factions"], dict):
            self._merge_factions(patch["factions"])

        self._merge_people(patch, vitals_touched)

        if isinstance(patch.get("resources"), dict):
            self.ensure_resources().merge_patch(patch["resources"])

        if isinstance(patch.get("challenges"), dict):
            self._merge_challenges(patch["challenges"])

        # Harita: `map` alanı + üstteki `location` değişikliği. İkisi de aynı
        # haritaya yazar, sıra önemli — önce yer kayıtları, sonra ana konum.
        if isinstance(patch.get("map"), dict):
            day = self.day if isinstance(self.day, int) else None
            self.ensure_map().merge_patch(patch["map"], day)

        # Seçenek havuzu: karakter başına liste TAMAMEN yenilenir (seçenekler
        # o tura aittir, birikmezler).
        if isinstance(patch.get("options"), dict):
            self._merge_options(patch["options"])

        # Kare harita: zemin değişiklikleri, yeni varlıklar, NPC hareketi.
        if isinstance(patch.get("grid"), dict):
            self._merge_grid(patch["grid"])

        # Tehdit: anlatıcının bildirdiği gürültü ve yoğunluk değişimi.
        if isinstance(patch.get("threat"), dict):
            self._merge_threat(patch["threat"])

        if "zombie_sightings_add" in patch and isinstance(patch["zombie_sightings_add"], list):
            seen = self.ensure_sightings()
            for item in patch["zombie_sightings_add"]:
                if item not in seen:
                    seen.append(item)

        if "flags" in patch and isinstance(patch["flags"], dict):
            self.ensure_flags().update(patch["flags"])

        if "narrator" in patch and isinstance(patch["narrator"], dict):
            self._merge_narrator(patch["narrator"])

    # --------------------------------------------------------------- parçalar
    def _merge_factions(self, patch: dict) -> None:
        self._touch("factions")
        for key, fields in patch.items():
            if not isinstance(fields, dict):
                continue
            faction = self.factions.get(key)
            if not isinstance(faction, Faction):
                faction = self.factions[key] = Faction.new()
            faction.merge_patch(fields)

    def _merge_people(self, patch: dict, vitals_touched: dict = None) -> None:
        """Oyuncu kadrosu (`characters`) kurulumda sabitlenir ve model
        tarafından GENİŞLETİLEMEZ. Model tanımadık bir ismi `characters`
        altına yazarsa (hikayede geçen birini oyuncu sanması, ya da isim
        uydurması) o kayıt sessizce `npcs`'e yönlendirilir — aksi halde
        uydurma isim rostere girip sonraki turlarda dünya durumuyla birlikte
        modele geri besleniyor ve kalıcılaşıyordu. Ters yön de düzeltilir:
        `npcs` altına yazılmış gerçek bir oyuncu karakteri `characters`'a
        geri alınır."""
        self._touch("characters")
        self._touch("npcs")
        for section in ("characters", "npcs"):
            if not isinstance(patch.get(section), dict):
                continue
            for name, fields in patch[section].items():
                if not isinstance(fields, dict):
                    continue
                day, clock = self.day, self.clock
                pc_key = canonical_name(self.characters, name)
                if pc_key:
                    key, person = pc_key, self.characters[pc_key]
                else:
                    key = canonical_name(self.npcs, name) or name
                    person = self.npcs.get(key)
                    if not isinstance(person, Person):
                        person = self.npcs[key] = Person.new()
                touched = person.merge_patch(fields, day, clock)
                if touched and vitals_touched is not None:
                    vitals_touched.setdefault(key, set()).update(touched)
                # Karakterin konumu değiştiyse harita da aynı turda taşınsın —
                # iki alanın ayrı ayrı yazılmasını beklemek, panelde grubun
                # eski yerde görünmesine yol açıyordu.
                if section == "characters" and isinstance(fields.get("location"), str) \
                        and fields["location"].strip():
                    self.ensure_map().place_person(key, fields["location"], self.day)

    def _merge_challenges(self, patch: dict) -> None:
        self._touch("challenges")
        for raw_name, fields in patch.items():
            if not isinstance(fields, dict):
                continue
            key = canonical_name(self.challenges, raw_name) or raw_name
            challenge = self.challenges.get(key)
            if not isinstance(challenge, Challenge):
                challenge = self.challenges[key] = Challenge.new()
            challenge.merge_patch(fields)

    def _merge_options(self, patch: dict) -> None:
        """Anlatıcının bu tur için sunduğu seçenekler.

        İsim eşlemesi kadroya göre yapılır: model "okan" yazsa da seçenekler
        "Okan"a düşer. Kadroda olmayan isim (NPC, uydurma) yok sayılır —
        seçenek yalnız oyuncu karakterine sunulur."""
        board = self.ensure_options()
        for raw_name, raw_list in patch.items():
            if not isinstance(raw_list, list):
                continue
            key = canonical_name(self.characters, raw_name)
            if not key:
                continue
            board.set_player(key, normalize_list(key, raw_list))

    def _merge_grid(self, patch: dict) -> None:
        """Kare haritanın yaması — sahneyi anlatıcı/GM şekillendirir.

        Desteklenen alanlar (hepsi opsiyonel):
          {"terrain": [{"x":3,"y":4,"type":"duvar"}],
           "spawn":   [{"id":"varil","name":"Yakıt varili","kind":"item","x":5,"y":6}],
           "remove":  ["varil"],
           "move":    [{"id":"Sevil","direction":"kuzey"}]}

        Oyuncu karakterlerinin konumu buradan DEĞİŞTİRİLEMEZ: onları yalnız
        oyuncunun kendi hamlesi (grid_service.move) hareket ettirir.
        """
        from .grid import KIND_PLAYER, Entity, move

        grid = self.ensure_grid()

        for kayit in patch.get("terrain") or []:
            if not isinstance(kayit, dict):
                continue
            x, y = as_int(kayit.get("x")), as_int(kayit.get("y"))
            tur = kayit.get("type") or kayit.get("terrain")
            if x is None or y is None or not isinstance(tur, str):
                continue
            grid.set_terrain(x, y, tur, kayit.get("passable"))

        for kayit in patch.get("spawn") or []:
            if not isinstance(kayit, dict):
                continue
            varlik = Entity.from_dict(kayit)
            if not varlik.id or varlik.kind == KIND_PLAYER:
                continue  # oyuncu karakteri buradan doğmaz
            grid.place(varlik, varlik.x, varlik.y)

        for varlik_id in patch.get("remove") or []:
            if isinstance(varlik_id, str):
                mevcut = grid.entity(varlik_id)
                if mevcut is not None and mevcut.kind != KIND_PLAYER:
                    grid.remove_entity(mevcut)

        for kayit in patch.get("move") or []:
            if not isinstance(kayit, dict):
                continue
            varlik = grid.entity(str(kayit.get("id") or ""))
            if varlik is None or varlik.kind == KIND_PLAYER:
                continue
            move(grid, varlik, kayit.get("direction"))

    def _merge_threat(self, patch: dict) -> None:
        """`threat` yaması — anlatıcı yalnız İKİ şeyi bildirir:

          {"noise_add": 25}                     bu turda çıkan gürültü
          {"density": {"Kuzey deposu": 30}}     bir yerin yeni ölü yoğunluğu

        Karşılaşmaların kendisi sunucunun zarıyla belirlenir; model buradan
        karşılaşma yazamaz, sayacı sıfırlayamaz."""
        threat = self.ensure_threat()

        eklenen = as_int(patch.get("noise_add"))
        if eklenen:
            threat.add_noise(max(-40, min(60, eklenen)))

        yogunluk = patch.get("density")
        if isinstance(yogunluk, dict):
            for yer, deger in yogunluk.items():
                sayi = as_int(deger)
                if isinstance(yer, str) and yer.strip() and sayi is not None:
                    threat.density[yer.strip()] = max(0, min(100, sayi))

    def _merge_narrator(self, npatch: dict) -> None:
        narrator = self.ensure_narrator()
        if isinstance(npatch.get("plot_summary"), str):
            narrator["plot_summary"] = npatch["plot_summary"]
        if isinstance(npatch.get("puzzles"), dict):
            puzzles = narrator.setdefault("puzzles", {})
            for name, fields in npatch["puzzles"].items():
                if isinstance(fields, dict):
                    puzzles.setdefault(name, {}).update(fields)
        if isinstance(npatch.get("upcoming_events"), dict):
            narrator.setdefault("upcoming_events", {}).update(npatch["upcoming_events"])
