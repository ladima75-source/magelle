SITE_URL = "https://magelle.com.ua"
STYLE_VERSION = "4.6"
APP_VERSION = "5.9"
MENU_VERSION = "2"

CANONICAL_DESIGNS = {
    "design-OF-MED-VYR": {"path": "/organic-flare-med-vyraznyi-pisochnyi.html", "base_color": "SND"},
    "design-OF-PER-VYR": {"path": "/organic-flare-vyraznyi-molochnyi.html", "base_color": "MLK"},
    "design-OF-KAR-VYR": {"path": "/organic-flare-vyraznyi-shokolad.html", "base_color": "CHO"},
    "design-OF-GNT-VYR": {"path": "/organic-flare-vyraznyi-hrafit.html", "base_color": "GRA"},
    "design-OF-DIM-VYR": {"path": "/organic-flare-dym-vyraznyi-bilyi.html", "base_color": "WHT"},
    "design-OF-BOR-DEL": {"path": "/organic-flare-delikatnyi-hrafit.html", "base_color": "GRA"},
    "design-OF-TER-DEL": {"path": "/organic-flare-delikatnyi-pisochnyi.html", "base_color": "SND"},
    "design-OF-LON-DEL": {"path": "/organic-flare-delikatnyi-molochnyi.html", "base_color": "MLK"},
    "design-OF-PUD-DEL": {"path": "/organic-flare-delikatnyi-bilyi.html", "base_color": "WHT"},
    "design-OF-OLI-DEL": {"path": "/organic-flare-delikatnyi-shokolad.html", "base_color": "CHO"},
    "design-AS-VRT-VYR": {"path": "/architectural-step-vertikal-vyraznyi-hrafit.html", "base_color": "GRA"},
    "design-AS-MON-VYR": {"path": "/architectural-step-monolit-vyraznyi-hrafit.html", "base_color": "GRA"},
    "design-AS-CNT-DEL": {"path": "/architectural-step-kontur-delikatnyi-hrafit.html", "base_color": "GRA"},
    "design-AS-RIT-DEL": {"path": "/architectural-step-ritm-delikatnyi-shokolad.html", "base_color": "CHO"},
    "design-SF-KOR-VYR": {"path": "/sculptural-fold-koral-vyraznyi.html", "base_color": "SND"},
    "design-SF-BUR-VYR": {"path": "/sculptural-fold-burshtyn-vyraznyi.html", "base_color": "CHO"},
}

# Historical URLs kept only so old external links do not hard-404.
# Each must be a lightweight noindex redirect, never a second PDP implementation.
LEGACY_REDIRECTS = {
    "organic-flare-vyraznyi-bilyi.html": {"target": "/organic-flare-dym-vyraznyi-bilyi.html", "canonical": SITE_URL + "/organic-flare-dym-vyraznyi-bilyi.html"},
    "organic-flare-vyraznyi-pisochnyi.html": {"target": "/organic-flare-med-vyraznyi-pisochnyi.html", "canonical": SITE_URL + "/organic-flare-med-vyraznyi-pisochnyi.html"},
    "architectural-step-vyraznyi-hrafit.html": {"target": "/architectural-step-vertikal-vyraznyi-hrafit.html", "canonical": SITE_URL + "/architectural-step-vertikal-vyraznyi-hrafit.html"},
    "architectural-step-vyraznyi-shokolad.html": {"target": "/architectural-step-monolit-vyraznyi-hrafit.html", "canonical": SITE_URL + "/architectural-step-monolit-vyraznyi-hrafit.html"},
    "architectural-step-delikatnyi-hrafit.html": {"target": "/architectural-step-kontur-delikatnyi-hrafit.html", "canonical": SITE_URL + "/architectural-step-kontur-delikatnyi-hrafit.html"},
    "architectural-step-delikatnyi-shokolad.html": {"target": "/architectural-step-ritm-delikatnyi-shokolad.html", "canonical": SITE_URL + "/architectural-step-ritm-delikatnyi-shokolad.html"},
    "architectural-step-delikatnyi-pisochnyi.html": {"target": "/architectural-step.html", "canonical": SITE_URL + "/architectural-step.html"},
    "architectural-step-vyraznyi-pisochnyi.html": {"target": "/architectural-step.html", "canonical": SITE_URL + "/architectural-step.html"},
    "organic-flare-med-vyraznyi-hrafit.html": {"target": "/organic-flare-med-vyraznyi-pisochnyi.html?color=GRA", "canonical": SITE_URL + "/organic-flare-med-vyraznyi-pisochnyi.html"},
    "organic-flare-dym-vyraznyi-hrafit.html": {"target": "/organic-flare-dym-vyraznyi-bilyi.html?color=GRA", "canonical": SITE_URL + "/organic-flare-dym-vyraznyi-bilyi.html"},
    "organic-flare-bordo-delikatnyi-shokolad.html": {"target": "/organic-flare-delikatnyi-hrafit.html?color=CHO", "canonical": SITE_URL + "/organic-flare-delikatnyi-hrafit.html"},
    "organic-flare-tera-delikatnyi-hrafit.html": {"target": "/organic-flare-delikatnyi-pisochnyi.html?color=GRA", "canonical": SITE_URL + "/organic-flare-delikatnyi-pisochnyi.html"},
    "organic-flare-lon-delikatnyi-hrafit.html": {"target": "/organic-flare-delikatnyi-molochnyi.html?color=GRA", "canonical": SITE_URL + "/organic-flare-delikatnyi-molochnyi.html"},
    "organic-flare-pudra-delikatnyi-hrafit.html": {"target": "/organic-flare-delikatnyi-bilyi.html?color=GRA", "canonical": SITE_URL + "/organic-flare-delikatnyi-bilyi.html"},
    "architectural-step-vertikal-vyraznyi-shokolad.html": {"target": "/architectural-step-vertikal-vyraznyi-hrafit.html?color=CHO", "canonical": SITE_URL + "/architectural-step-vertikal-vyraznyi-hrafit.html"},
    "architectural-step-monolit-vyraznyi-shokolad.html": {"target": "/architectural-step-monolit-vyraznyi-hrafit.html?color=CHO", "canonical": SITE_URL + "/architectural-step-monolit-vyraznyi-hrafit.html"},
    "architectural-step-kontur-delikatnyi-shokolad.html": {"target": "/architectural-step-kontur-delikatnyi-hrafit.html?color=CHO", "canonical": SITE_URL + "/architectural-step-kontur-delikatnyi-hrafit.html"},
    "architectural-step-ritm-delikatnyi-hrafit.html": {"target": "/architectural-step-ritm-delikatnyi-shokolad.html?color=GRA", "canonical": SITE_URL + "/architectural-step-ritm-delikatnyi-shokolad.html"},
}
LEGACY_PATHS = set(LEGACY_REDIRECTS)

EXPECTED_CATALOG_DESIGNS = 16
