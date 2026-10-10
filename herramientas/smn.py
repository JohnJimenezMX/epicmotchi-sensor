"""Descarga el pronóstico del Servicio Meteorológico Nacional (CONAGUA) y deja en smn.json solo el municipio
más cercano a la ubicación guardada en el puente. Lo corre GitHub Actions cada 3 horas.
Las horas del SMN vienen en hora local; "dh" es la diferencia con UTC en horas."""
import gzip, json, math, os, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

SMN = "https://smn.conagua.gob.mx/tools/GUI/webservices/?method={}"


def bajar(url, intentos=3):
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "epicmotchi-sensor (GitHub Actions)"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:  # el SMN a veces tarda o se cae
            print(f"Intento {i + 1}: {e}", file=sys.stderr)
            time.sleep(20)
    raise SystemExit("No pude descargar " + url)


def smn(metodo):
    datos = bajar(SMN.format(metodo))
    return json.loads(gzip.decompress(datos) if datos[:2] == b"\x1f\x8b" else datos)


def distancia(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def epoch_local(texto, dh):  # "20261009T07" en hora local, dh = horas atrás de UTC
    t = datetime.strptime(texto, "%Y%m%dT%H").replace(tzinfo=timezone.utc) + timedelta(hours=int(dh))
    return int(t.timestamp())


def num(x):
    try:
        return round(float(x), 1)
    except (TypeError, ValueError):
        return None


def main():
    puente = os.environ["PUENTE_URL"]
    aj = json.loads(bajar(puente + "?vista=sensor&minutos=10"))["ajustes"]
    lat, lon = float(aj["lat"]), float(aj["lon"])

    horas = smn(3)
    llave = lambda x: (x["ides"], x["idmun"])
    municipios = {}
    for x in horas:
        municipios.setdefault(llave(x), x)
    mejor = min(municipios.values(), key=lambda x: distancia(lat, lon, float(x["lat"]), float(x["lon"])))
    k = llave(mejor)
    mias = sorted((x for x in horas if llave(x) == k), key=lambda x: x["hloc"])
    dias = sorted((x for x in smn(1) if llave(x) == k), key=lambda x: x["ndia"])

    salida = {
        "esquema": "epicmotchi.smn.v1",
        "fuente": "Servicio Meteorológico Nacional (CONAGUA)",
        "descargado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "municipio": mejor["nmun"], "estado": mejor["nes"],
        "lat": float(mejor["lat"]), "lon": float(mejor["lon"]),
        "distancia_km": round(distancia(lat, lon, float(mejor["lat"]), float(mejor["lon"])), 1),
        "horas": [{
            "epoch": epoch_local(x["hloc"], x["dh"]), "temp": num(x["temp"]), "hr": num(x["hr"]), "dpt": num(x["dpt"]),
            "prec": num(x["prec"]), "probprec": num(x["probprec"]), "viento": num(x["velvien"]),
            "dirviento": x.get("dirvienc"), "cielo": x.get("desciel"),
        } for x in mias],
        "dias": [{
            "fecha": x["dloc"][:8], "tmax": num(x["tmax"]), "tmin": num(x["tmin"]), "probprec": num(x["probprec"]),
            "prec": num(x["prec"]), "cielo": x.get("desciel"),
        } for x in dias],
    }
    with open("smn.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{mejor['nmun']}, {mejor['nes']}: {len(mias)} horas, {len(dias)} días")


if __name__ == "__main__":
    main()
