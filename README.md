# ResearchGate Data Hub

This repository contains tools and processed data related to publications extracted
from [ResearchGate](https://www.researchgate.net/).

## Data Structure: `nodes.csv` (Publications Metadata)

The  `nodes.csv` [file](src/researchgate_hub/processed/nodes.csv) contains comprehensive metadata for individual
publications, often originating from the output of
the scraping processes.

| Column Name         | Data Type      | Description                                                                              | Example Value                                                                                                      | 
|---------------------|----------------|------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| **publication_id**  | String         | Unique ResearchGate identifier for the publication (prefixed with `PB:`).                | `PB:350696830`                                                                                                     | 
| **url**             | String         | Direct URL to the publication page on ResearchGate.                                      | `https://www.researchgate.net/publication/350696830`                                                               | 
| **title**           | String         | Full title of the publication.                                                           | `Machine Learning Modeling: A New Way to do Quantitative Research in Social Sciences...`                           | 
| **type**            | String         | Type of publication (e.g., `article`, `preprint`, `data`).                               | `article`                                                                                                          | 
| **authors**         | List\[String\] | List of authors associated with the work. Encoded as a bracketed string in the CSV.      | `['Caihua Shan', 'Nikos Mamoulis']`                                                                                | 
| **year**            | Float          | Publication year (often included in raw data).                                           | `2021.0`                                                                                                           | 
| **abstract**        | String         | Summary or abstract of the publication.                                                  | `Improvements in big data and machine learning algorithms have helped AI technologies reach a new breakthrough...` | 
| **citations_count** | Float          | Number of citations recorded for this work (in raw data).                                | `12.0`                                                                                                             | 
| **topics**          | List\[String\] | List of associated research topics/tags. Encoded as a bracketed string in the CSV.       | `['machine-learning-sociology']`                                                                                   | 
| **raw**             | Boolean        | Flag indicating if this record was processed from raw JSON input (`True` if successful). | `True`                                                                                                             |_