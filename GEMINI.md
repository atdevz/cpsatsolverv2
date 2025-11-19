# Project Overview

This project is a sophisticated employee scheduling application that uses Google's OR-Tools, specifically the CP-SAT solver, to generate optimal work schedules. It's designed to handle complex constraints and objectives common in workforce management, such as ensuring required shift coverage, respecting employee availability and qualifications, and balancing workload. The application also includes a web-based interface built with Flask for managing the input data.

## Key Technologies

*   **Backend:** Python
*   **Core Library:** Google OR-Tools (CP-SAT Solver)
*   **Data Manipulation:** Pandas
*   **Web Framework:** Flask
*   **Data Format:** JSON for input and output, with CSV for the final schedule.

## Architecture

The application is divided into three main parts:

1.  **Core Solver Engine (`src/`):**
    *   `data_loader.py`: Loads all necessary data from JSON files (employees, shifts, daily needs, etc.).
    *   `models.py`: Defines the data structures for employees, shifts, and other entities.
    *   `solver.py`: The main CP-SAT solver. It builds the constraint model, defines hard and soft constraints, and finds an initial solution.
    *   `refinement_solver.py`: An additional solver that attempts to improve upon the initial solution iteratively.
    *   `reporter.py`: Generates a human-readable report from the solver's output.
    *   `main.py`: The main entry point for the command-line application. It orchestrates the data loading, solving, and reporting process.

2.  **Web Application (`web_app/`):**
    *   `app.py`: A Flask application that provides a web interface for managing the input data.
    *   `data_manager.py`: Handles the reading and writing of the JSON data files.
    *   `templates/`: Contains the HTML templates for the web interface.

3.  **Data (`data/`):**
    *   `input/`: Contains the input JSON files for employees, shifts, daily needs, etc.
    *   `output/`: The destination for the generated schedule (CSV) and report (text file).

# Building and Running

## Prerequisites

*   Python 3
*   The required Python packages listed in `requirements.txt`.

## Installation

1.  Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Solver (Command Line)

To run the scheduling solver from the command line:

```bash
python main.py
```

This will:
1.  Load the data from the `data/input/` directory.
2.  Run the initial solver and then the refinement solver.
3.  Save the final schedule to `data/output/planning_final.csv`.
4.  Save a detailed report to `data/output/planning_report_final.txt`.

## Running the Web Application

To start the Flask web application for managing the data:

```bash
python web_app/app.py
```

The application will be available at `http://127.0.0.1:5000`.

# Development Conventions

*   **Configuration:** The main configuration for the solver is in `config/settings.json`. This includes penalties for soft constraints, time limits for the solver, and other parameters.
*   **Input Data:** All input data is stored in JSON files in the `data/input/` directory. The web application provides a user-friendly way to edit this data.
*   **Testing:** The `tests/` directory is set up for unit tests, but no tests are currently implemented.
