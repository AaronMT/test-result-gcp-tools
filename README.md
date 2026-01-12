# test-result-gcp-tools

A collection of scripts and GitHub Actions workflows for automating test result ingestion and crash report processing from Google Cloud Storage (GCS) and Firebase Test Lab.

## Purpose

This repository provides automation tools for:

- **Crash Report Processing**: Downloading, symbolicating, and processing Android minidump crash reports from Firebase Test Lab
- **Test Result Ingestion**: Parsing JUnit XML test reports and ingesting them into various reporting platforms (Allure, ReportPortal, Google Sheets, BigQuery)
- **Test Statistics Aggregation**: Collecting and aggregating test automation metrics for dashboards and reporting

## GitHub Actions Workflows

| Workflow | Description |
|----------|-------------|
| `batch-crash-report` | Processes Android minidump crash reports from Firebase Test Lab, symbolicates them using Mozilla crash symbols, and sends Slack notifications |
| `batch-ingest-allure` | Ingests JUnit XML reports from GCS into Allure for test result visualization |
| `batch-ingest-report-portal` | Ingests JUnit XML reports from GCS into ReportPortal |
| `batch-ingest-sheets` | Aggregates JUnit XML reports and uploads metrics to Google Sheets and BigQuery |
| `tae-ingest-sheets` | Ingests Test Automation Engineering (TAE) statistics from Allure to Google Sheets |
| `validate-staging-table` | Validates BigQuery staging table data |
| `debug-bq` | Debug utility for BigQuery setup verification |

## Who Is This For?

This repository is intended for **Mozilla's Firefox Mobile Test Operations team** working on Fenix (Firefox for Android) and Focus (Firefox Focus for Android) projects. It automates the collection, processing, and reporting of test results from Firebase Test Lab runs.
