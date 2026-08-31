"""Recomendaciones de productos reales disponibles."""
import re
import unicodedata
from db import connect

PROFILES={
 "calor":(["camiseta","algodon","blusa","vestido","falda","short","bermuda","sandalia","gorra","playa"],["bufanda","lana","polar","chompa","chaqueta","bota"]),
 "frio":(["chompa","chaqueta","buzo","bufanda","lana","polar","bota"],["sandalia","playa"]),
 "deporte":(["deport","leggins","jogger","bra","zapatilla","dri-fit"],[]),
 "playa":(["playa","sandalia","vestido","gorra","camiseta","short"],["bota","bufanda","chompa"]),
 "formal":(["elegante","blusa","vestido","pantalon","cuero","clasico"],["playa","deport"]),
 "trabajo":(["blusa","camisa","pantalon","clasico","casual"],["playa"]),
 "casual":(["casual","jean","camiseta","zapatilla","jogger"],[]),
 "lluvia":(["bota","chaqueta"],["sandalia"])
}
def plain(value):
 return "".join(c for c in unicodedata.normalize("NFKD",str(value).lower()) if not unicodedata.combining(c))
def recommend_products(need,limit=3,max_price=None,size=None):
 limit=max(1,min(int(limit or 3),5)); query=plain(need); active=[]
 for intent,(positive,negative) in PROFILES.items():
  if intent in query or (intent=="calor" and any(x in query for x in ("caliente","verano"))): active.append((intent,positive,negative))
 with connect() as conn:
  rows=[dict(r) for r in conn.execute("""SELECT vp.id_variante id,p.nombre_producto producto,vp.sku,c.nombre_categoria categoria,
   t.etiqueta talla,co.nombre color,COALESCE(vp.precio_venta_override,p.precio_venta)::float precio,i.cantidad_disponible::int stock
   FROM public.variantes_producto vp JOIN public.productos p USING(id_producto) JOIN public.categorias c USING(id_categoria)
   JOIN public.tallas t USING(id_talla) JOIN public.colores co ON co.id_color=vp.id_color_principal
   JOIN public.inventario i USING(id_variante) WHERE vp.activo AND i.cantidad_disponible>0
   AND (%s::numeric IS NULL OR COALESCE(vp.precio_venta_override,p.precio_venta)<=%s)
   AND (%s::text IS NULL OR lower(t.etiqueta)=lower(%s)) ORDER BY i.cantidad_disponible DESC""",(max_price,max_price,size,size)).fetchall()]
 scored=[]; terms=[x for x in re.findall(r"[a-z0-9]+",query) if len(x)>3]
 for row in rows:
  text=plain(" ".join(str(row[k]) for k in ("producto","categoria","color","talla"))); score=min(row["stock"],100)/100; reasons=[]
  for intent,positive,negative in active:
   hits=[word for word in positive if word in text]; misses=[word for word in negative if word in text]; score+=3*len(hits)-4*len(misses)
   if hits: reasons.append("Afinidad con "+intent+" inferida por: "+", ".join(hits[:3]))
  direct=[word for word in terms if word in text]; score+=2*len(direct)
  if direct: reasons.append("Coincide con la solicitud: "+", ".join(direct[:3]))
  if not active and not direct: score+=row["stock"]/100
  if score>0: scored.append((score,row,reasons))
 scored.sort(key=lambda item:(item[0],item[1]["stock"]),reverse=True)
 products=[]; seen=set()
 for _,row,reasons in scored:
  if not size and row["producto"] in seen: continue
  seen.add(row["producto"])
  products.append({**row,"motivos":reasons or ["Producto disponible con stock"],"advertencia":"La adecuación se infiere del nombre y la categoría; no hay datos de material, grosor ni transpirabilidad."})
  if len(products)>=limit: break
 return {"fuente":"PostgreSQL RopaV","necesidad":need,"criterios":{"talla":size,"precio_maximo":max_price,"solo_con_stock":True},"productos":products,"limitaciones":["No existen campos de material, temporada, grosor o transpirabilidad.","Las propiedades no registradas son inferencias, no hechos."]}