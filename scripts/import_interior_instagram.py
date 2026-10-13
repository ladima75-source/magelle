#!/usr/bin/env python3
"""One-time import of already-public MaGelle interior-first Instagram slides."""
import io, json, time
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image
SOURCES = json.loads("[{\"filename\":\"step-vertical-interior.webp\",\"post\":\"https://www.instagram.com/magelle_flowers/p/DeOb4xXCIcG/\",\"url\":\"https://scontent-phl2-1.cdninstagram.com/v/t51.82787-15/839158037_18117050497917023_6891339014542257579_n.jpg?stp=dst-jpg_e35_tt6&_nc_cat=108&ig_cache_key=NDAwMzI1OTQyNDc1OTYzMDcyNg%3D%3D.3-ccb7-5&ccb=7-5&_nc_sid=58cdad&efg=eyJ2ZW5jb2RlX3RhZyI6IkNBUk9VU0VMX0lURU0ueHBpZHMuMTA4MC5zZHIucmVndWxhcl9waG90by5DMyJ9&_nc_ohc=787JK774vdoQ7kNvwFLkM22&_nc_oc=AdoGW4BGwOIN6DAp9uV46QjfjBPcpP119tl1AMfRaRkmYpu9ueMvKa-7o0jB5fytQwAZGazSIJEE-FwQG6GyGMe-&_nc_zt=23&_nc_ht=scontent-phl2-1.cdninstagram.com&_nc_gid=yBmmdovFkSUYo2diGA35rw&_nc_ss=7b289&oh=00_AQMdpIgNCX71jWCPnftI1MGp2NC3xcQJZI0bLSqQg_ieqg&oe=6AD429EA\"},{\"filename\":\"organic-graphite-evening.webp\",\"post\":\"https://www.instagram.com/magelle_flowers/p/DeOcC01CJC7/\",\"url\":\"https://scontent-sea5-1.cdninstagram.com/v/t51.82787-15/840697995_18117050752917023_9063251900064190729_n.jpg?stp=dst-jpg_e35_tt6&_nc_cat=108&ig_cache_key=NDAwMzI2MDA5MjIxNjAzMDI4Ng%3D%3D.3-ccb7-5&ccb=7-5&_nc_sid=58cdad&efg=eyJ2ZW5jb2RlX3RhZyI6IkNBUk9VU0VMX0lURU0ueHBpZHMuMTA4MC5zZHIucmVndWxhcl9waG90by5DMyJ9&_nc_ohc=7cKKwRmEJaAQ7kNvwFbcDeA&_nc_oc=AdrB2a7CiuLTdExOMJLhUZrQsj8YDAdVwUKE3qrBrWdRAChF9aiKNv5RoJSKlJtXjSM&_nc_zt=23&_nc_ht=scontent-sea5-1.cdninstagram.com&_nc_gid=WFCxXQ8Pro8RbtOsCs-J7A&_nc_ss=7ba8c&oh=00_AQOQ-ftxRb4uQNhdZpzHkilv888vJgwgIi6X90meF2ACAA&oe=6AD42189\"},{\"filename\":\"organic-wine-interior.webp\",\"post\":\"https://www.instagram.com/magelle_flowers/p/DeOcUXDiGBy/\",\"url\":\"https://scontent-phl2-1.cdninstagram.com/v/t51.82787-15/840923207_18117051106917023_1948156334140657292_n.jpg?stp=dst-jpg_e35_tt6&_nc_cat=107&ig_cache_key=NDAwMzI2MTI3NjAyNDc1MjQzOQ%3D%3D.3-ccb7-5&ccb=7-5&_nc_sid=58cdad&efg=eyJ2ZW5jb2RlX3RhZyI6IkNBUk9VU0VMX0lURU0ueHBpZHMuMTA4MC5zZHIucmVndWxhcl9waG90by5DMyJ9&_nc_ohc=8o0VK667eL0Q7kNvwHx2Ru_&_nc_oc=Adprl4CFYEV6MNxoHl53aV_XZdSoM0lBXPJ-ABjZ1CV6zKyBokIC_nr0-Vdjpxo6WEWLCfeRfy4eDL3K8PNhhtEe&_nc_zt=23&_nc_ht=scontent-phl2-1.cdninstagram.com&_nc_gid=JHlMPeKbJxv9kaoWYECKWw&_nc_ss=7ba8c&oh=00_AQO93uF3x1J3rv2-TUmfcGjRc_YKfXxOpxN0eTWHdR6-DA&oe=6AD4417B\"},{\"filename\":\"organic-milk-soft-light.webp\",\"post\":\"https://www.instagram.com/magelle_flowers/p/DeOcd4lCFmR/\",\"url\":\"https://scontent-lga3-2.cdninstagram.com/v/t51.82787-15/838614335_18117051373917023_9043929413503649783_n.jpg?stp=dst-jpg_e35_tt6&_nc_cat=100&ig_cache_key=NDAwMzI2MTk1MDk2MzgwMDAyMg%3D%3D.3-ccb7-5&ccb=7-5&_nc_sid=58cdad&efg=eyJ2ZW5jb2RlX3RhZyI6IkNBUk9VU0VMX0lURU0ueHBpZHMuMTA4MC5zZHIucmVndWxhcl9waG90by5DMyJ9&_nc_ohc=EU7qzzvukqYQ7kNvwFfr9RF&_nc_oc=AdpnPoJiCrxhwAGlbxprLSLnA38WcJ6Po19e38VhXyVfiMMwcrwsAQdJMXGcfczJkMg&_nc_zt=23&_nc_ht=scontent-lga3-2.cdninstagram.com&_nc_gid=rqVqzN__g6qnbsNJxGvKbA&_nc_ss=7b289&oh=00_AQOM2oYSfy8dAy135PDHMUIY-VhVlgcwVnQlSAwAdr5hqA&oe=6AD43469\"},{\"filename\":\"organic-coral-wood.webp\",\"post\":\"https://www.instagram.com/magelle_flowers/p/DeOcooyiAXQ/\",\"url\":\"https://scontent-lga3-1.cdninstagram.com/v/t51.82787-15/841120903_18117051568917023_7140479229733281916_n.jpg?stp=dst-jpg_e35_tt6&_nc_cat=111&ig_cache_key=NDAwMzI2MjYyNzQ4ODIzNjc1OA%3D%3D.3-ccb7-5&ccb=7-5&_nc_sid=58cdad&efg=eyJ2ZW5jb2RlX3RhZyI6IkNBUk9VU0VMX0lURU0ueHBpZHMuMTA4MC5zZHIucmVndWxhcl9waG90by5DMyJ9&_nc_ohc=NN6nY2PR4ZcQ7kNvwEdVVEj&_nc_oc=AdorWjCd4FG8aJGsHJbXzn_vI2ezEfvzD_3YaH6Aw9pkD-Y3GUpD2gl8yz_K3I1ow1E&_nc_zt=23&_nc_ht=scontent-lga3-1.cdninstagram.com&_nc_gid=nt4Gwv0Qw-VSAq8EaA58uw&_nc_ss=7b289&oh=00_AQMHCXEYN-zh_FCqri242T2MarTgyRbI9q3hJZDsEdwsyQ&oe=6AD40EAD\"},{\"filename\":\"step-pair-interior.webp\",\"post\":\"https://www.instagram.com/magelle_flowers/p/DeOcyZoiCNO/\",\"url\":\"https://scontent-bos5-1.cdninstagram.com/v/t51.82787-15/840881742_18117051910917023_9217768405989202722_n.jpg?stp=dst-jpg_e35_tt6&_nc_cat=106&ig_cache_key=NDAwMzI2MzM2ODg5ODU5MTAyMg%3D%3D.3-ccb7-5&ccb=7-5&_nc_sid=58cdad&efg=eyJ2ZW5jb2RlX3RhZyI6IkNBUk9VU0VMX0lURU0ueHBpZHMuMTA4MC5zZHIucmVndWxhcl9waG90by5DMyJ9&_nc_ohc=md0ZJGllzkoQ7kNvwEhj5t9&_nc_oc=AdoSZDwFC-gC4BbDmkYHBC7XOzIQvBmCRaQvvO79RCI5rI_2xmPk4xs-uTuk4uM0UKsyfhB5KoDQ2hTbPclY2Tup&_nc_zt=23&_nc_ht=scontent-bos5-1.cdninstagram.com&_nc_gid=FaXmjnWt2qmSgl7MeRFW6A&_nc_ss=7b289&oh=00_AQOGA6Gxz1Bo5C14wdSqw9se_H1XyGR7-NQqqwsLFBUXnw&oe=6AD437BF\"},{\"filename\":\"organic-milk-dining.webp\",\"post\":\"https://www.instagram.com/magelle_flowers/p/DeOdBZTiNGa/\",\"url\":\"https://scontent-hou1-1.cdninstagram.com/v/t51.82787-15/839960525_18117052165917023_6092791223620051417_n.jpg?stp=dst-jpg_e35_tt6&_nc_cat=103&ig_cache_key=NDAwMzI2NDM3NjMxMTY2NDczNg%3D%3D.3-ccb7-5&ccb=7-5&_nc_sid=58cdad&efg=eyJ2ZW5jb2RlX3RhZyI6IkNBUk9VU0VMX0lURU0ueHBpZHMuMTA4MC5zZHIucmVndWxhcl9waG90by5DMyJ9&_nc_ohc=TiI5J4v1MHMQ7kNvwHKuKnZ&_nc_oc=AdrFFCwTe5YO85tH_7OhJKydJGCrLwnZNVxZNIsg_EPCSPd-jEZVLKmNMqGAbvDUR60&_nc_zt=23&_nc_ht=scontent-hou1-1.cdninstagram.com&_nc_gid=03Sp-t6lKCNWNKknA6tTiA&_nc_ss=7b689&oh=00_AQOlIDGw7PdSzhykDmw543GDzQJmKUVoXAn14BTSlClJTA&oe=6AD412D6\"}]")
OUT = Path("media/interiors")
OUT.mkdir(parents=True,exist_ok=True)
for source in SOURCES:
    content = None
    for attempt in range(3):
        try:
            req=Request(source["url"],headers={
              "User-Agent":"Mozilla/5.0 (compatible; MaGelle-media-archive/1.0)",
              "Referer":"https://www.instagram.com/"
            })
            with urlopen(req,timeout=35) as response:
                mime=response.headers.get_content_type()
                if mime not in ("image/jpeg","image/png","image/webp"):
                    raise ValueError(f"Unexpected content-type {mime}")
                content=response.read(9*1024*1024)
                break
        except Exception:
            if attempt==2: raise
            time.sleep(2*(attempt+1))
    image=Image.open(io.BytesIO(content))
    image.load()
    if min(image.size)<450:
        raise ValueError("Image too small to publish: "+source["filename"]+" "+str(image.size))
    image=image.convert("RGB")
    image.thumbnail((1200,1500),Image.Resampling.LANCZOS)
    output=OUT/source["filename"]
    image.save(output,"WEBP",quality=83,method=6)
    print("READY",output,image.size,output.stat().st_size,"from",source["post"])
