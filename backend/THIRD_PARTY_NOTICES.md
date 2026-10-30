# Mentions tierces

## LAYA — Convai Innovations

- Code : [`src/chatbot_api/laya_runtime.py`](src/chatbot_api/laya_runtime.py) est adapté du
  paquet `laya` 0.4.17 (`laya/common.py`, `laya/onnx_agent.py`) —
  <https://github.com/NandhaKishorM/laya>.
- Modèles (téléchargés à la demande par `scripts/download_laya_model.py`, non inclus dans le
  dépôt) : `convaiinnovations/laya` (configuration et tokenizer de la variante anglaise),
  exports ONNX communautaires `mnjkshrm/sentrygate-laya` et
  `soyelmismo/laya-multilingual-onnx`.
- Copyright Convai Innovations et contributeurs.
- Licence : Apache License 2.0 — <https://www.apache.org/licenses/LICENSE-2.0>.

Modifications apportées au code : extraction du seul chemin d'inférence ONNX, sans dépendance
à PyTorch ni à `transformers` (tokenizer chargé avec la bibliothèque `tokenizers`) ;
suppression du réordonnancement des options, des étiquettes `noul` personnalisées, de la
calibration par histogramme, des températures par langue et du traitement par lots.
