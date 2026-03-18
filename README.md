
# NPR Project

## Overview
This project is a Python-based system for data extraction, graph storage, and processing. It is designed to handle large datasets efficiently and provide robust data manipulation capabilities.

## Core Components

### 1. Data Extraction (`extraction.py`)
- Handles reading and parsing input data files (e.g., JSON, TXT).
- Cleans and structures raw data for downstream processing.
- Trade-off: Simplicity vs. flexibility. The extraction logic is kept simple for maintainability, but may require adaptation for new data formats.

### 2. Graph Storage (`graph_store.py`)
- Implements data structures for storing and querying graphs.
- Supports operations like adding nodes/edges, searching, and traversals.
- Trade-off: In-memory storage is fast and easy to implement, but may not scale to extremely large graphs. For larger datasets, consider using a database or graph-specific storage engine.

### 3. Main Logic (`main.py`)
- Orchestrates the workflow: extraction → graph storage → processing.
- Handles error management and logging.
- Trade-off: Centralized control simplifies debugging and flow management, but can become a bottleneck if the workflow grows complex. Modularization is recommended for future scalability.

### 4. Data Models (`models.py`)
- Defines Python classes and data structures for representing entities and relationships.
- Ensures type safety and clarity in data handling.
- Trade-off: Explicit models improve code readability and maintainability, but require updates when data schema changes.

### 5. Dependencies (`requirements.txt`)
- Lists required Python packages for reproducibility.
- Trade-off: Using minimal dependencies reduces complexity and potential conflicts, but may limit available features. Add packages as needed for advanced functionality.

## Design Decisions & Trade-offs

- **Simplicity vs. Scalability:** The project favors simple, readable code for ease of maintenance. For production-scale workloads, consider integrating database storage or distributed processing.
- **In-memory Processing:** Fast for small to medium datasets, but not suitable for very large graphs. For scalability, use external storage solutions.
- **Modular Structure:** Each component is separated for clarity and future extensibility. This makes it easier to test and update individual parts.
- **Error Handling:** Centralized in `main.py` for easier debugging, but can be refactored into custom exception classes for more granular control.

## Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/NaplesVentureLLP/NPR.git
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
- Run the main script:
  ```bash
  python main.py
  ```

## License
MIT License

## Contact
For questions, contact Naples Venture LLP.
