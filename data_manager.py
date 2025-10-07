import pandas as pd
import os

def load_ubicaciones(path):
    if os.path.exists(path):
        df = pd.read_excel(path)
        df.columns = [col.strip() for col in df.columns]
        df = df.drop_duplicates(subset="Proyecto", keep="first")
        return df
    else:
        return pd.DataFrame(columns=["Proyecto", "Latitud", "Longitud"])

def save_ubicaciones(df, path):
    df.to_excel(path, index=False)

def add_proyecto(df, nombre, lat, lon):
    if nombre and not df["Proyecto"].eq(nombre).any():
        new_row = pd.DataFrame([{"Proyecto": nombre, "Latitud": lat, "Longitud": lon}])
        return pd.concat([df, new_row], ignore_index=True)
    return df

def update_proyecto(df, nombre, lat, lon):
    df.loc[df["Proyecto"] == nombre, ["Latitud", "Longitud"]] = [lat, lon]
    return df

def delete_proyecto(df, nombre):
    return df[df["Proyecto"] != nombre]
