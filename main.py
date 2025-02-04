import json
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from fpdf import FPDF


# Funzione per caricare dati stipendi medi
def carica_dati_stipendi():
    with open("stipendi_medi.json", "r", encoding="utf-8") as file:
        return json.load(file)["stipendi"]

# Funzione per calcolare la tassazione dei fringe benefit
def calcola_fringe_benefit(fringe_benefit, figli):
   """Determina la parte esente e imponibile dei fringe benefit."""
   soglia_esenzione = 2000 if figli > 0 else 1000  # Esente fino a 2000€ con figli, 1000€ senza

   if fringe_benefit > soglia_esenzione:
      fringe_imponibile = fringe_benefit - soglia_esenzione
      fringe_esente = soglia_esenzione
   else:
      fringe_imponibile = 0
      fringe_esente = fringe_benefit

   return fringe_esente, fringe_imponibile

def calcola_addizionale_regionale(reddito_imponibile, regione):
    """Calcola l'addizionale regionale basata sulla regione e sugli scaglioni."""
    aliquote_regionali = {
        "Lombardia": [(15000, 0.0123), (28000, 0.0158), (50000, 0.0172), (float("inf"), 0.0173)],
        #"Lazio": [(15000, 0.013), (28000, 0.016), (50000, 0.018), (float("inf"), 0.019)],
        #"Veneto": [(15000, 0.012), (28000, 0.015), (50000, 0.017), (float("inf"), 0.018)],
    }

    if regione not in aliquote_regionali:
        return 0  # Se la regione non è nella lista, assumiamo 0

    aliquote = aliquote_regionali[regione]
    addizionale_regionale = 0
    precedente_soglia = 0

    for soglia, aliquota in aliquote:
        if reddito_imponibile > soglia:
            addizionale_regionale += (soglia - precedente_soglia) * aliquota
            precedente_soglia = soglia
        else:
            addizionale_regionale += (reddito_imponibile - precedente_soglia) * aliquota
            break

    return round(addizionale_regionale, 2)

# Funzione per calcolare la detrazione per lavoro dipendente
def calcola_detrazione_lavoro(reddito_imponibile, tempo_determinato=False):
   if reddito_imponibile <= 15000:
      detrazione = 1955
      detrazione = max(detrazione, 690 if not tempo_determinato else 1380)
   elif reddito_imponibile <= 28000:
      detrazione = 1910 + (1190 * (28000 - reddito_imponibile) / 13000)
   elif reddito_imponibile <= 50000:
      detrazione = 1910 * (50000 - reddito_imponibile) / 22000
   else:
      detrazione = 0
   return round(detrazione, 2)

# Funzione per calcolare il taglio cuneo fiscale 2025
def calcola_taglio_cuneo_fiscale(reddito_imponibile):
   if reddito_imponibile <= 8500:
      bonus = reddito_imponibile * 0.071
   elif reddito_imponibile <= 15000:
      bonus = reddito_imponibile * 0.053
   elif reddito_imponibile <= 20000:
      bonus = reddito_imponibile * 0.048
   else:
      bonus = 0

   if 20000 < reddito_imponibile <= 32000:
      bonus += 1000
   elif 32000 < reddito_imponibile <= 40000:
      bonus += max(0, 1000 * (40000 - reddito_imponibile) / 8000)

   return round(bonus, 2)

def calcola_detrazione_coniuge(reddito_complessivo):
   """
   Calcola la detrazione per il coniuge a carico in base al reddito complessivo.
   """
   if reddito_complessivo <= 15000:
      detrazione = 800 - (110 * (reddito_complessivo / 15000))
   elif 15001 <= reddito_complessivo <= 29000:
      detrazione = 690
   elif 29001 <= reddito_complessivo <= 35000:
      detrazione = 700
   elif 35001 <= reddito_complessivo <= 40000:
      detrazione = 710
   elif 40001 <= reddito_complessivo <= 80000:
      detrazione = 690 * ((80000 - reddito_complessivo) / 40000)
   else:
      detrazione = 0
   return round(detrazione, 2)

def calcola_detrazione_figli(reddito_complessivo, numero_figli):
   """
   Calcola la detrazione per figli a carico in base al reddito complessivo, al numero di figli,
   alla loro età.
   """
   detrazione_totale = 0
   for i in range(numero_figli):
      detrazione_base = 950


      incremento = (numero_figli - 1) * 15000
      soglia = 95000 + incremento
      quoziente = (soglia - reddito_complessivo) / soglia

      if quoziente > 0:
         detrazione = detrazione_base * quoziente
      else:
         detrazione = 0

      detrazione_totale += detrazione

   return round(detrazione_totale, 2)



# Funzione per calcolare la RAL corretta con scaglioni IRPEF
def calcola_stipendio_netto(ral, mensilita, regione, addizionale_comunale, coniuge, figli, fringe_imponibile, fringe_esente):
   fattore_contributi_inps = 0.0919  # Contributi previdenziali (9,19%)

   # Calcolo del reddito imponibile
   reddito_imponibile = (ral * (1 - fattore_contributi_inps)) + fringe_imponibile
   inps = ral * fattore_contributi_inps

   # Scaglioni IRPEF 2025
   scaglioni = [(28000, 0.23), (50000, 0.35), (float("inf"), 0.43)]
   irpef = 0
   restante = reddito_imponibile
   precedente_soglia = 0

   for soglia, aliquota in scaglioni:
      if restante > (soglia - precedente_soglia):
         irpef += (soglia - precedente_soglia) * aliquota
         restante -= (soglia - precedente_soglia)
      else:
         irpef += restante * aliquota
         break
      precedente_soglia = soglia

   addizionale_regionale = calcola_addizionale_regionale(reddito_imponibile, regione)

   # Addizionale Comunale (in base all'input utente)
   addizionale_comunale_importo = (addizionale_comunale / 100) * reddito_imponibile  

   detrazione_lavoro = calcola_detrazione_lavoro(reddito_imponibile)
   imposta_netta_senza_bonus = irpef + addizionale_regionale + addizionale_comunale_importo - detrazione_lavoro

   # Detrazioni per familiari a carico (stima)
   detrazione_familiari = calcola_detrazione_coniuge(ral) + calcola_detrazione_figli(ral, figli) 

   # Taglio Cuneo Fiscale
   bonus_cuneo_fiscale = calcola_taglio_cuneo_fiscale(reddito_imponibile)

    # Calcolo finale dello stipendio netto
    
   tasse_totali = imposta_netta_senza_bonus  - detrazione_familiari
   stipendio_netto_annuo = reddito_imponibile - tasse_totali + bonus_cuneo_fiscale + fringe_esente
   stipendio_netto_mensile = stipendio_netto_annuo / mensilita

   # Calcolo costo aziendale
   contributi_azienda = 0.30  # Circa il 30% aggiuntivo sui costi aziendali
   costo_aziendale = ral * (1 + contributi_azienda) + fringe_benefit

   return (
      round(stipendio_netto_annuo, 2),
      round(stipendio_netto_mensile, 2),
      round(tasse_totali, 2),
      round(costo_aziendale, 2),
      round(reddito_imponibile, 2),
      round(inps, 2),
      round(irpef, 2),
      round(detrazione_lavoro, 2),
      round(addizionale_regionale, 2),
      round(addizionale_comunale_importo, 2)
   )

# Caricamento dati sugli stipendi
stipendi_data = carica_dati_stipendi()
df_stipendi = pd.DataFrame(stipendi_data)

# UI Streamlit migliorata
st.title("💼 Calcolatore Stipendio Netto & Costo Aziendale ")

# Selezione professione e dati personali
professione = st.selectbox("Seleziona la professione:", df_stipendi["professione"])
ral = st.number_input("Inserisci la Retribuzione Annua Lorda (RAL) (€):", min_value=1000, max_value=200000, step=1000)
mensilita = st.selectbox("Numero di mensilità:", [12, 13, 14])
regione = st.selectbox("Regione di residenza:", ["Lombardia"])
st.markdown('[ℹ️ Consulta le addizionali comunali](https://www1.finanze.gov.it/finanze2/dipartimentopolitichefiscali/fiscalitalocale/nuova_addcomirpef/sceltaregione.htm)', unsafe_allow_html=True)
addizionale_comunale = st.slider(
    "Addizionale comunale (%)",
    0.0, 1.5, 0.8, 0.05,
    help="Seleziona l'aliquota dell'addizionale comunale in base al tuo comune."
)

# Opzioni aggiuntive
#buono_pasto = st.selectbox("Buono Pasto:", ["No", "Sì"])
coniuge = st.checkbox("Coniuge a carico")
figli = st.number_input("Figli minori di 21 anni a carico:", min_value=0, max_value=10, step=1)
fringe_benefit = st.number_input("Inserisci il valore annuo dei fringe benefit (€)", min_value=0, max_value=5000, step=100)
# Calcola la parte esente e imponibile
fringe_esente, fringe_imponibile = calcola_fringe_benefit(fringe_benefit, figli)
# Calcolo nuovo reddito imponibile con fringe benefit imponibile


# Calcolo dello stipendio netto
if st.button("Calcola Stipendio Netto & Costo Aziendale"):
   stipendio_netto_annuo, stipendio_netto_mensile, tasse_totali, costo_aziendale, reddito_imponibile, inps, irpef, detrazione_lavoro, addizionale_regionale, addizionale_comunale = calcola_stipendio_netto(ral, mensilita, regione, addizionale_comunale, coniuge, figli, fringe_imponibile, fringe_esente)

   # Recupero dati di mercato per il confronto
   dati_professione = df_stipendi[df_stipendi["professione"] == professione].iloc[0]
   ral_media_mercato = dati_professione["ral_media"]

   # Output dei risultati
   # Creazione del DataFrame con i risultati
   df_risultati = pd.DataFrame(data = {
      "Descrizione": [
         "Retribuzione Annua Lorda (RAL)", "Contributi INPS Pagati", "Reddito Imponibile",
         "IRPEF", "Addizionale Regionale", "Addizionale Comunale",
         "Detrazione Lavoro Dipendente", "Fringe Benefit",
         "Tasse Totali Pagate", "Stipendio Netto Annuo", "Stipendio Netto Mensile",
         "Costo Aziendale Totale"
      ],
      "Importo (€)": [
         ral, inps, reddito_imponibile,
         irpef, addizionale_regionale, addizionale_comunale,
         detrazione_lavoro, fringe_benefit,
         tasse_totali, stipendio_netto_annuo, stipendio_netto_mensile,
         costo_aziendale
      ]
   })

   # Mostra il DataFrame come tabella in Streamlit
   st.subheader("📌 Risultati del Calcolo")
   st.write("Ecco i dettagli del calcolo del tuo stipendio netto e del costo aziendale:")

   st.table(df_risultati)

   # Confronto con il mercato
   st.subheader("📊 Confronto con la Media di Mercato")
   st.markdown("La tua RAL è stata confrontata con la media di mercato per la tua professione. (Al momento valori non affidabili)")
   if ral > ral_media_mercato:
      st.success(f"✅ La tua RAL è **superiore** alla media di mercato ({ral_media_mercato} €)")
   elif ral == ral_media_mercato:
      st.success(f"🟢 La tua RAL è **pari** alla media di mercato ({ral_media_mercato} €)")
   else:
      st.warning(f"🔺 La tua RAL è **minore** alla media di mercato ({ral_media_mercato} €)")


   st.subheader("📊 Distribuzione del Reddito")

   addizionali = addizionale_regionale + addizionale_comunale
   labels = ["Stipendio Netto", "IRPEF", "Inps", "Addizionali"]
   valori = [stipendio_netto_annuo, irpef, inps, addizionali]

   fig1, ax1 = plt.subplots()

   # Creazione del grafico a torta SENZA percentuali sopra
   wedges, texts = ax1.pie(
      valori, labels=None, startangle=90, colors=["#4CAF50", "#FF5733", "#FFC300", "#3498db"]
   )

   # Creazione della legenda con le percentuali
   percentuali = [f"{label}: {val:.1f}%" for label, val in zip(labels, [(v / sum(valori)) * 100 for v in valori])]
   ax1.legend(wedges, percentuali, title="Legenda", loc="center left", bbox_to_anchor=(1, 0.5))

   ax1.axis("equal")  # Assicura che il grafico sia un cerchio perfetto
   st.pyplot(fig1)

   # Grafico a barre per costo aziendale
   st.subheader("📊 Costo Aziendale vs Stipendio Netto")
   st.markdown("Al momento il costo aziendale è calcolato con la RAL per fattore moltiplicativo 1.3")
   categorie = ["Stipendio Netto Annuo", "Costo Aziendale"]
   valori_costo = [stipendio_netto_annuo, costo_aziendale]

   fig2, ax2 = plt.subplots()
   ax2.bar(categorie, valori_costo, color=["#4CAF50", "#FF5733", "#e74c3c"])
   ax2.set_ylabel("Importo (€)")
   ax2.set_title("Confronto tra Costo Aziendale e Stipendio Netto")
   st.pyplot(fig2)

   st.divider()
   st.header("Altre cose che vorrei implementare:")
   st.write("1. Variazione costo aziendale in base ad aumento RAL (con impatto fringe benefit più preciso)")
   st.write("1b. PopUp che rimanda a consulente per diminuire costo aziendale")
   st.write("2. Calcolo detrazioni con più eventualità (es. figli con età diverse)")
   st.write("3. Aggiungere più regioni e comuni per le addizionali")
   st.write("4. Implementare più professioni e dati di mercato per il confronto")
   st.write("5. Aggiungere la possibilità di scaricare il report in PDF")
   st.write("6. Aggiungere la possibilità di salvare i dati inseriti per un confronto futuro")
   st.write("7. Aggiungere la possibilità di inserire tipologie di contratto diverse (es. part-time, full-time)")


