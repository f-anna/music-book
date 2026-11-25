Models found: vadbert, pert, fiction, stories, goemotions, emolit

## Speed and memory (passages, 16 x ~700 words)

| Model | Load (s) | Peak RSS (MB) | s / 1000 words | s / passage | Truncated items |
|---|---|---|---|---|---|
| vadbert | 1.2 | 1250 | 3.03 | 2.2 | 5 |
| pert | 78.0 | 2234 | 20.2 | 14.5 | 2 |
| fiction | 71.3 | 1998 | 12.05 | 8.7 | 1 |
| stories | 134.7 | 2018 | 117.54 | 84.7 | 4 |
| goemotions | 3.6 | 1185 | 3.17 | 2.3 | 6 |
| emolit | 84.9 | 2162 | 12.75 | 9.2 | 1 |

## Spread of the passage means (700 words)

| Model.dim | min | max | range / scale | std / scale | sentence-level std / scale |
|---|---|---|---|---|---|
| vadbert.V | 2.774 | 3.073 | 0.075 | 0.022 | 0.070 |
| vadbert.A | 3.059 | 3.511 | 0.113 | 0.031 | 0.081 |
| pert.V | 2.832 | 3.218 | 0.097 | 0.022 | 0.074 |
| pert.A | -0.079 | 0.451 | 0.265 | 0.066 | 0.174 |
| fiction.V | -0.522 | 0.206 | 0.364 | 0.093 | 0.229 |
| stories.V | 0.203 | 0.690 | 0.488 | 0.110 | 0.165 |
| stories.A | 0.243 | 0.578 | 0.335 | 0.099 | 0.192 |
| goemotions.V | -0.061 | 0.115 | 0.088 | 0.024 | 0.106 |
| goemotions.A | 0.329 | 0.440 | 0.110 | 0.025 | 0.082 |
| goemotions.T | 0.007 | 0.138 | 0.132 | 0.031 | 0.087 |
| emolit.T | 0.251 | 0.483 | 0.232 | 0.062 | 0.202 |

## Spearman rho vs. the provisional V/A/T labels (16 passages; |rho| >= 0.50 ~ p < 0.05)

| Model.dim | mean 700 | p10 700 | p90 700 | -low 700 | high 700 | mean 300 | best 300 | vs Qwen (7, mean 700) |
|---|---|---|---|---|---|---|---|---|
| vadbert.V | +0.45 | +0.56 | +0.25 | +0.45 | +0.22 | +0.29 | +0.56 (p10) | +0.77 |
| vadbert.A | +0.44 | +0.23 | +0.38 | +0.37 | +0.45 | +0.25 | +0.27 (high) | +0.36 |
| pert.V | +0.50 | +0.43 | +0.05 | +0.73 | +0.30 | +0.35 | +0.58 (-low) | +0.86 |
| pert.A | +0.62 | +0.31 | +0.83 | +0.24 | +0.71 | +0.55 | +0.55 (mean) | +0.64 |
| fiction.V | +0.41 | +0.59 | +0.15 | +0.49 | +0.13 | +0.33 | +0.60 (p10) | +0.77 |
| stories.V | +0.57 | +0.69 | +0.57 | +0.68 | +0.47 | +0.58 | +0.71 (p10) | +0.67 |
| stories.A | +0.63 | +0.29 | +0.82 | +0.42 | +0.62 | +0.60 | +0.64 (high) | +0.54 |
| goemotions.V | +0.34 | +0.56 | +0.11 | +0.12 | +0.04 | +0.24 | +0.44 (p10) | +0.80 |
| goemotions.A | +0.09 | +0.06 | +0.36 | -0.14 | -0.03 | -0.19 | +0.05 (p10) | -0.37 |
| goemotions.T | +0.33 | +0.20 | +0.57 | +0.18 | +0.17 | +0.33 | +0.36 (p90) | +0.00 |
| emolit.T | +0.57 | +0.18 | +0.57 | +0.39 | +0.67 | +0.28 | +0.59 (high) | +0.85 |

## The old method (300-word chunks, word-weighted mean) vs. sentence-level, 700 words

| Model.dim | chunk: range / scale | sentence mean: range / scale | chunk: rho | sentence mean: rho | sentence best: rho |
|---|---|---|---|---|---|
| vadbert.V | 0.126 | 0.075 | +0.50 | +0.45 | +0.56 |
| vadbert.A | 0.156 | 0.113 | +0.36 | +0.44 | +0.45 |
| goemotions.V | 0.261 | 0.088 | +0.32 | +0.34 | +0.56 |
| goemotions.A | 0.121 | 0.110 | +0.21 | +0.09 | +0.36 |
| goemotions.T | 0.175 | 0.132 | +0.48 | +0.33 | +0.57 |

## Agreement between the models, V (Spearman of the passage means, 700 words)

| | vadbert | pert | fiction | stories | goemotions |
|---|---|---|---|---|---|
| vadbert | +1.00 | +0.86 | +0.90 | +0.65 | +0.60 |
| pert | +0.86 | +1.00 | +0.78 | +0.74 | +0.57 |
| fiction | +0.90 | +0.78 | +1.00 | +0.78 | +0.49 |
| stories | +0.65 | +0.74 | +0.78 | +1.00 | +0.41 |
| goemotions | +0.60 | +0.57 | +0.49 | +0.41 | +1.00 |

## Agreement between the models, A (Spearman of the passage means, 700 words)

| | vadbert | pert | stories | goemotions |
|---|---|---|---|---|
| vadbert | +1.00 | +0.89 | +0.90 | +0.40 |
| pert | +0.89 | +1.00 | +0.85 | +0.31 |
| stories | +0.90 | +0.85 | +1.00 | +0.22 |
| goemotions | +0.40 | +0.31 | +0.22 | +1.00 |

## goemotions: atmosphere labels (annotations_e2.csv) via the emotion mapping, average precision

| Label | chance | mean 700 | p90 700 | mean 300 | p90 300 |
|---|---|---|---|---|---|
| ominous | 0.44 | 0.64 | 0.67 | 0.63 | 0.81 |
| suspenseful | 0.19 | 0.33 | 0.29 | 0.53 | 0.26 |
| mysterious | 0.12 | 0.70 | 0.38 | 0.67 | 0.75 |
| melancholic | 0.31 | 0.87 | 0.87 | 0.75 | 0.70 |
| warm and cozy | 0.12 | 0.25 | 0.35 | 0.18 | 0.45 |
| peaceful | 0.19 | 0.42 | 0.40 | 0.39 | 0.29 |
| oppressive | 0.38 | 0.50 | 0.49 | 0.64 | 0.49 |
| whimsical | 0.25 | 0.28 | 0.20 | 0.20 | 0.22 |
| wondrous | 0.19 | 0.28 | 0.25 | 0.44 | 0.61 |
| **macro** | 0.24 | **0.48** | **0.43** | **0.49** | **0.51** |

## emolit: atmosphere labels (annotations_e2.csv) via the emotion mapping, average precision

| Label | chance | mean 700 | p90 700 | mean 300 | p90 300 |
|---|---|---|---|---|---|
| ominous | 0.44 | 0.80 | 0.73 | 0.51 | 0.69 |
| suspenseful | 0.19 | 0.51 | 0.72 | 0.48 | 0.76 |
| mysterious | 0.12 | 0.38 | 0.42 | 0.45 | 1.00 |
| melancholic | 0.31 | 0.86 | 0.70 | 0.83 | 0.66 |
| warm and cozy | 0.12 | 0.70 | 0.39 | 0.58 | 0.45 |
| peaceful | 0.19 | 0.92 | 0.79 | 0.92 | 1.00 |
| oppressive | 0.38 | 0.66 | 0.66 | 0.49 | 0.77 |
| whimsical | 0.25 | 0.22 | 0.25 | 0.20 | 0.26 |
| wondrous | 0.19 | 0.23 | 0.21 | 0.28 | 0.23 |
| **macro** | 0.24 | **0.59** | **0.54** | **0.53** | **0.65** |

## Windows (300 words), z-scored window means per column

### CHAPTER 132. The Symphony.

| win | begins | vadbe.V | vadbe.A | pert.V | pert.A | ficti.V | stori.V | stori.A | goemo.V | goemo.A | goemo.T | emoli.T |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | It was a clear steel-blue day.… | +0.6 | -1.5 | +0.6 | -0.9 | +0.8 | +0.1 | -1.5 | +0.5 | -0.8 | -0.6 | +0.4 |
| 300 | Slowly crossing the deck from the… | +0.1 | +0.4 | -0.2 | -0.1 | +0.1 | +0.6 | +0.2 | +1.0 | +1.1 | +0.2 | -0.3 |
| 600 | Guinea-coast slavery of solitary command!—when I… | -2.3 | +1.9 | -2.2 | +2.3 | -2.0 | -2.4 | +1.4 | -2.5 | +1.2 | +2.5 | +2.5 |
| 900 | Close! stand close to me, Starbuck;… | +1.1 | +0.9 | +1.6 | +0.7 | +1.5 | +0.3 | +1.0 | +0.7 | +0.3 | -0.3 | -0.1 |
| 1200 | Yes, yes! no more! it is… | -0.3 | -0.2 | -0.0 | -0.4 | -0.2 | -0.5 | +1.0 | +0.3 | +1.2 | -0.3 | -0.6 |
| 1500 | Sleeping?… | -0.3 | -1.0 | -0.1 | -1.1 | -0.4 | +0.4 | -0.2 | +0.2 | -1.2 | -0.7 | -0.7 |
| 1800 | “Nothing, nothing sir!” was the sound… | +0.2 | -0.1 | -0.1 | -0.2 | -0.6 | +1.0 | -0.9 | -0.3 | -1.0 | -0.6 | -0.9 |
| 2100 | “He’s going to sound!… | +0.8 | -0.5 | +0.4 | -0.4 | +0.9 | +0.4 | -1.0 | +0.2 | -0.7 | -0.1 | -0.2 |

### CHAPTER 3. The Spouter-Inn.

| win | begins | vadbe.V | vadbe.A | pert.V | pert.A | ficti.V | stori.V | stori.A | goemo.V | goemo.A | goemo.T | emoli.T |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Entering that gable-ended Spouter-Inn, you found… | +0.7 | -0.3 | +0.1 | +0.2 | +0.4 | +0.2 | -0.4 | -0.2 | -0.1 | -0.1 | -1.0 |
| 300 | But stop; does it not bear… | -1.3 | -0.2 | -0.3 | -0.6 | -0.5 | +0.7 | -0.6 | -1.3 | -0.5 | +0.5 | +0.1 |
| 600 | A still duskier place is this,… | -0.4 | -0.6 | +0.3 | -0.7 | -0.3 | -0.1 | -0.5 | -1.1 | -1.0 | -0.2 | -0.8 |
| 900 | I s’pose you are goin’ a-whalin’,… | -0.1 | -1.2 | -0.3 | -0.9 | -0.9 | +0.9 | -0.9 | +0.1 | -0.8 | -0.5 | -0.0 |
| 1200 | “Oh, no,” said he, looking a… | +0.1 | -0.2 | +1.0 | +0.3 | +0.3 | +1.0 | -0.2 | +1.1 | -0.1 | -0.3 | -0.5 |
| 1500 | The liquor soon mounted into their… | +1.4 | -0.2 | +1.5 | +0.2 | +0.7 | +0.9 | -0.9 | +1.6 | -0.6 | -0.5 | -0.9 |
| 1800 | It was now about nine o’clock,… | +0.8 | -1.2 | +0.1 | -0.4 | +0.1 | -0.2 | +0.2 | +0.1 | +0.5 | -0.5 | +0.0 |
| 2100 | “But wait a bit, Skrimshander; I’ve… | +0.5 | -1.0 | +0.7 | -0.1 | +1.0 | +0.5 | -0.2 | +0.0 | -0.6 | -0.5 | -0.6 |
| 2400 | The devil fetch that harpooneer, thought… | -0.7 | +1.9 | -0.8 | +1.5 | -0.2 | -0.3 | +0.5 | +1.2 | +1.2 | -0.2 | +1.2 |
| 2700 | “That’s precisely it,” said the landlord,… | -1.8 | +1.5 | -2.3 | +2.0 | -2.1 | -1.7 | +1.7 | -0.7 | +0.2 | +0.0 | +1.8 |
| 3000 | “Wall,” said the landlord, fetching a… | +0.1 | +1.0 | +0.4 | +1.2 | +0.7 | +0.5 | -0.4 | +0.2 | -0.3 | -0.4 | -0.7 |
| 3300 | Why, afore we give it up,… | +1.1 | -0.4 | +1.2 | -1.7 | +1.3 | +1.2 | -1.2 | +0.3 | -1.6 | -0.5 | -0.4 |
| 3600 | Likewise, there was a parcel of… | +0.7 | -0.1 | +0.4 | -1.0 | +0.0 | +0.5 | -0.8 | +0.7 | -0.6 | -0.5 | +0.3 |
| 3900 | Whether that mattress was stuffed with… | -0.1 | +0.6 | -0.2 | -0.7 | +0.9 | -1.3 | +1.1 | +0.2 | +0.6 | +0.6 | +0.2 |
| 4200 | They were stains of some sort… | +1.0 | -1.4 | +0.1 | -0.7 | +0.9 | -0.2 | -0.1 | +0.4 | +0.8 | -0.4 | -1.1 |
| 4500 | His bald purplish head now looked… | -2.1 | +1.6 | -2.1 | +1.3 | -2.2 | -2.4 | +2.6 | -2.5 | +2.8 | +3.7 | +2.5 |
