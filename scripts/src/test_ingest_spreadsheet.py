#!/usr/bin/env python3
"""
Unit tests for ingest_spreadsheet.py
Tests the key functions modified for upsert logic and date consistency.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest_spreadsheet import (
    calculate_overall_totals,
    update_daily_totals_sheet,
)


class TestCalculateOverallTotals(unittest.TestCase):
    """Tests for calculate_overall_totals function"""
    
    def setUp(self):
        self.sample_results = [
            {
                "Class Name": "TestClass1",
                "Test Name": "test1",
                "Total Runs": 10,
                "Flaky Runs": 2,
                "Failed Runs": 1,
                "Flaky Rate": "20.00%",
                "Failure Rate": "10.00%",
            },
            {
                "Class Name": "TestClass2",
                "Test Name": "test2",
                "Total Runs": 20,
                "Flaky Runs": 3,
                "Failed Runs": 2,
                "Flaky Rate": "15.00%",
                "Failure Rate": "10.00%",
            },
        ]
    
    def test_calculate_overall_totals_with_explicit_date(self):
        """Test that explicit run_date is used in output"""
        test_date = "2024-01-15"
        result = calculate_overall_totals(self.sample_results, run_date=test_date)
        
        self.assertEqual(result["Date"], test_date)
        self.assertEqual(result["Total Runs"], 30)
        self.assertEqual(result["Flaky Runs"], 5)
        self.assertEqual(result["Failed Runs"], 3)
        self.assertEqual(result["Flaky Rate"], "16.67%")
        self.assertEqual(result["Failure Rate"], "10.00%")
    
    def test_calculate_overall_totals_defaults_to_yesterday(self):
        """Test that run_date defaults to yesterday when not provided"""
        result = calculate_overall_totals(self.sample_results)
        
        expected_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        self.assertEqual(result["Date"], expected_date)
    
    def test_calculate_overall_totals_with_none_date(self):
        """Test that run_date=None defaults to yesterday"""
        result = calculate_overall_totals(self.sample_results, run_date=None)
        
        expected_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        self.assertEqual(result["Date"], expected_date)
    
    def test_calculate_overall_totals_empty_results(self):
        """Test that empty results return zeros"""
        result = calculate_overall_totals([], run_date="2024-01-15")
        
        self.assertEqual(result["Date"], "2024-01-15")
        self.assertEqual(result["Total Runs"], 0)
        self.assertEqual(result["Flaky Runs"], 0)
        self.assertEqual(result["Failed Runs"], 0)
        self.assertEqual(result["Flaky Rate"], "0.00%")
        self.assertEqual(result["Failure Rate"], "0.00%")


class TestUpdateDailyTotalsSheet(unittest.TestCase):
    """Tests for update_daily_totals_sheet function"""
    
    def setUp(self):
        self.daily_totals = {
            "Date": "2024-01-15",
            "Total Runs": 100,
            "Flaky Runs": 10,
            "Failed Runs": 5,
            "Flaky Rate": "10.00%",
            "Failure Rate": "5.00%",
        }
        self.project_name = "Focus"
        self.sheet_name = "Daily Totals"
    
    @patch('ingest_spreadsheet.with_retries')
    @patch('ingest_spreadsheet.time.sleep')
    def test_update_creates_headers_if_missing(self, mock_sleep, mock_with_retries):
        """Test that headers are created if the sheet is empty"""
        # Mock client and sheet
        mock_client = Mock()
        mock_sheet = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_sheet
        mock_client.open.return_value = mock_spreadsheet
        
        # Setup mock responses - call the function passed to with_retries
        def with_retries_side_effect(func):
            return func()
        
        mock_with_retries.side_effect = with_retries_side_effect
        mock_sheet.row_values.return_value = []
        mock_sheet.get_all_values.return_value = [[]]
        mock_sheet.append_row.return_value = None
        
        # Call the function
        update_daily_totals_sheet(mock_client, self.daily_totals, self.sheet_name, self.project_name)
        
        # Verify with_retries was called for operations
        self.assertGreater(mock_with_retries.call_count, 0)
    
    @patch('ingest_spreadsheet.with_retries')
    @patch('ingest_spreadsheet.time.sleep')
    @patch('builtins.print')
    def test_update_appends_new_row_when_no_match(self, mock_print, mock_sleep, mock_with_retries):
        """Test that a new row is appended when no existing match is found"""
        # Mock client and sheet
        mock_client = Mock()
        mock_sheet = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_sheet
        mock_client.open.return_value = mock_spreadsheet
        
        # Setup mock responses - call the function passed to with_retries
        def with_retries_side_effect(func):
            return func()
        
        mock_with_retries.side_effect = with_retries_side_effect
        mock_sheet.row_values.return_value = ["Date", "Project Name", "Total Runs", "Flaky Runs", "Failed Runs", "Flaky Rate", "Failure Rate"]
        mock_sheet.get_all_values.return_value = [
            ["Date", "Project Name", "Total Runs", "Flaky Runs", "Failed Runs", "Flaky Rate", "Failure Rate"],
            ["2024-01-14", "Fenix", "90", "8", "4", "8.89%", "4.44%"]
        ]
        mock_sheet.append_row.return_value = None
        
        # Call the function
        update_daily_totals_sheet(mock_client, self.daily_totals, self.sheet_name, self.project_name)
        
        # Verify append was called
        mock_sheet.append_row.assert_called()
        # Verify log message
        mock_print.assert_any_call(f"[Daily Totals] Appended new row for {self.project_name} on 2024-01-15")
    
    @patch('ingest_spreadsheet.with_retries')
    @patch('ingest_spreadsheet.time.sleep')
    @patch('builtins.print')
    def test_update_modifies_existing_row_when_match_found(self, mock_print, mock_sleep, mock_with_retries):
        """Test that existing row is updated when (Date, Project Name) matches"""
        # Mock client and sheet
        mock_client = Mock()
        mock_sheet = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_sheet
        mock_client.open.return_value = mock_spreadsheet
        
        # Setup mock responses - call the function passed to with_retries
        def with_retries_side_effect(func):
            return func()
        
        mock_with_retries.side_effect = with_retries_side_effect
        mock_sheet.row_values.return_value = ["Date", "Project Name", "Total Runs", "Flaky Runs", "Failed Runs", "Flaky Rate", "Failure Rate"]
        mock_sheet.get_all_values.return_value = [
            ["Date", "Project Name", "Total Runs", "Flaky Runs", "Failed Runs", "Flaky Rate", "Failure Rate"],
            ["2024-01-15", "Focus", "90", "8", "4", "8.89%", "4.44%"]
        ]
        mock_sheet.update.return_value = None
        
        # Call the function
        update_daily_totals_sheet(mock_client, self.daily_totals, self.sheet_name, self.project_name)
        
        # Verify update was called
        mock_sheet.update.assert_called()
        # Verify log message
        mock_print.assert_any_call(f"[Daily Totals] Updated existing row 2 for {self.project_name} on 2024-01-15")
    
    @patch('ingest_spreadsheet.with_retries')
    @patch('ingest_spreadsheet.time.sleep')
    @patch('builtins.print')
    def test_focus_and_fenix_separate_rows(self, mock_print, mock_sleep, mock_with_retries):
        """Test that Focus and Fenix create separate rows for the same date"""
        # Mock client and sheet
        mock_client = Mock()
        mock_sheet = Mock()
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_sheet
        mock_client.open.return_value = mock_spreadsheet
        
        # Setup mock responses - call the function passed to with_retries
        def with_retries_side_effect(func):
            return func()
        
        mock_with_retries.side_effect = with_retries_side_effect
        mock_sheet.row_values.return_value = ["Date", "Project Name", "Total Runs", "Flaky Runs", "Failed Runs", "Flaky Rate", "Failure Rate"]
        mock_sheet.get_all_values.return_value = [
            ["Date", "Project Name", "Total Runs", "Flaky Runs", "Failed Runs", "Flaky Rate", "Failure Rate"],
            ["2024-01-15", "Fenix", "80", "6", "3", "7.50%", "3.75%"]
        ]
        mock_sheet.append_row.return_value = None
        
        # Call the function with Focus project
        update_daily_totals_sheet(mock_client, self.daily_totals, self.sheet_name, "Focus")
        
        # Verify append was called (new row for Focus)
        mock_sheet.append_row.assert_called()
        # Verify log message indicates new row
        mock_print.assert_any_call(f"[Daily Totals] Appended new row for Focus on 2024-01-15")


if __name__ == "__main__":
    unittest.main()
