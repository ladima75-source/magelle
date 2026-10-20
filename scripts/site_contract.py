SITE_URL = "https://magelle.com.ua"
STYLE_VERSION = "4.6"
APP_VERSION = "5.4"
MENU_VERSION = "2"

# Historical URLs kept only so old external links do not hard-404.
# Each must be a lightweight noindex redirect, never a second PDP implementation.
LEGACY_REDIRECTS = {
    "organic-flare-vyraznyi-bilyi.html": {
        "target": "/organic-flare-dym-vyraznyi-hrafit.html?color=WHT",
        "canonical": SITE_URL + "/organic-flare-dym-vyraznyi-hrafit.html",
    },
    "organic-flare-vyraznyi-pisochnyi.html": {
        "target": "/organic-flare-med-vyraznyi-hrafit.html?color=SND",
        "canonical": SITE_URL + "/organic-flare-med-vyraznyi-hrafit.html",
    },
    "architectural-step-vyraznyi-hrafit.html": {
        "target": "/architectural-step-vertikal-vyraznyi-shokolad.html?color=GRA",
        "canonical": SITE_URL + "/architectural-step-vertikal-vyraznyi-shokolad.html",
    },
    "architectural-step-vyraznyi-shokolad.html": {
        "target": "/architectural-step-monolit-vyraznyi-shokolad.html?color=GRA",
        "canonical": SITE_URL + "/architectural-step-monolit-vyraznyi-shokolad.html",
    },
    "architectural-step-delikatnyi-hrafit.html": {
        "target": "/architectural-step-kontur-delikatnyi-shokolad.html?color=GRA",
        "canonical": SITE_URL + "/architectural-step-kontur-delikatnyi-shokolad.html",
    },
    "architectural-step-delikatnyi-shokolad.html": {
        "target": "/architectural-step-ritm-delikatnyi-hrafit.html?color=CHO",
        "canonical": SITE_URL + "/architectural-step-ritm-delikatnyi-hrafit.html",
    },
    "architectural-step-delikatnyi-pisochnyi.html": {
        "target": "/architectural-step.html",
        "canonical": SITE_URL + "/architectural-step.html",
    },
    "architectural-step-vyraznyi-pisochnyi.html": {
        "target": "/architectural-step.html",
        "canonical": SITE_URL + "/architectural-step.html",
    },
}
LEGACY_PATHS = set(LEGACY_REDIRECTS)

EXPECTED_CATALOG_DESIGNS = 15
