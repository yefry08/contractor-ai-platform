#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 19 15:07:42 2024

@author: dduque
"""

#Original From Daniel Duque Lozano
# -*- coding: utf-8 -*-

import pandas as pd
import os
import plotly.express as px
import matplotlib.pyplot as plt
from plotly.subplots import make_subplots
import plotly.graph_objs as go


import streamlit as st

st.set_page_config(layout='wide')


filtrado1=pd.read_excel(
    r"Data/resultados finales/resultados.xlsx")

filtrado1=filtrado1.rename(columns={"predict": "Valor Proyectado", "value_million_dolar": "Valor real","likelihood":"Similitud de valor"})
extrange="Tamaño valor extraño"
filtrado1[extrange]=(filtrado1["Valor real"]-filtrado1["Valor Proyectado"]*2)
filtrado1["range-"]=filtrado1["Valor Proyectado"]/2
st.title("contratación pública")

tab0,tab1 = st.tabs(['selección','second'])
with tab0:
    
  
    
    resulting=filtrado1.sort_values("Tamaño valor extraño",ascending=False)

    
    resulting=resulting[["compiledRelease/buyer/name","compiledRelease/planning/budget/description","compiledRelease/id",
                         "Valor real","Valor Proyectado",extrange,"Similitud de valor"]]      

    
    
    st.dataframe(resulting.style.background_gradient(axis=None, cmap="Reds"))
    
    
    
    
  
