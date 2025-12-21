"""
Flask application for Provar Test Report Analyzer
Supports XML, PDF, and Automation API reports
"""

from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json

# Import extractors
from xml_extractor import extract_failures, compare_reports
from pdf_extractor import extract_pdf_failures
from api_xml_extractor import extract_api_failures, compare_api_reports

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xml', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Storage for baselines
baseline_storage = {
    'xml': None,
    'pdf': None,
    'api': None
}


def allowed_file(filename, report_type='xml'):
    """Check if file extension is allowed"""
    if report_type == 'pdf':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'
    else:  # xml or api
        return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'xml'


# ============================================================================
# ROUTES - HOME & INFO
# ============================================================================

@app.route('/')
def index():
    """Home page - redirect to XML analyzer"""
    return render_template('index.html')


@app.route('/about')
def about():
    """About page with tool information"""
    return render_template('about.html')


# ============================================================================
# ROUTES - XML REPORTS
# ============================================================================

@app.route('/xml')
def xml_analyzer():
    """XML Report analyzer page"""
    return render_template('xml_analyzer.html')


@app.route('/api/xml/upload', methods=['POST'])
def upload_xml():
    """Handle XML file upload and analysis"""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename, 'xml'):
        return jsonify({'error': 'Invalid file type. Please upload XML file'}), 400
    
    try:
        # Extract failures
        failures = extract_failures(file)
        
        # Store in session
        session['current_xml_failures'] = failures
        session['current_xml_filename'] = file.filename
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'failures': failures,
            'total_failures': len([f for f in failures if not f.get('_no_failures', False)])
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@app.route('/api/xml/set-baseline', methods=['POST'])
def set_xml_baseline():
    """Set current report as baseline for XML"""
    
    if 'current_xml_failures' not in session:
        return jsonify({'error': 'No current report to set as baseline'}), 400
    
    baseline_storage['xml'] = {
        'failures': session['current_xml_failures'],
        'filename': session.get('current_xml_filename', 'Unknown'),
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'message': 'Baseline set successfully',
        'baseline_filename': baseline_storage['xml']['filename']
    })


@app.route('/api/xml/compare', methods=['POST'])
def compare_xml():
    """Compare current XML report with baseline"""
    
    if 'current_xml_failures' not in session:
        return jsonify({'error': 'No current report uploaded'}), 400
    
    if baseline_storage['xml'] is None:
        return jsonify({'error': 'No baseline set. Please set a baseline first'}), 400
    
    try:
        current = session['current_xml_failures']
        baseline = baseline_storage['xml']['failures']
        
        comparison = compare_reports(current, baseline)
        
        return jsonify({
            'success': True,
            'comparison': comparison,
            'current_filename': session.get('current_xml_filename', 'Current'),
            'baseline_filename': baseline_storage['xml']['filename']
        })
        
    except Exception as e:
        return jsonify({'error': f'Error comparing reports: {str(e)}'}), 500


@app.route('/api/xml/baseline-info', methods=['GET'])
def xml_baseline_info():
    """Get information about current XML baseline"""
    
    if baseline_storage['xml'] is None:
        return jsonify({'has_baseline': False})
    
    return jsonify({
        'has_baseline': True,
        'filename': baseline_storage['xml']['filename'],
        'timestamp': baseline_storage['xml']['timestamp'],
        'failure_count': len([f for f in baseline_storage['xml']['failures'] 
                            if not f.get('_no_failures', False)])
    })


# ============================================================================
# ROUTES - PDF REPORTS
# ============================================================================

@app.route('/pdf')
def pdf_analyzer():
    """PDF Report analyzer page"""
    return render_template('pdf_analyzer.html')


@app.route('/api/pdf/upload', methods=['POST'])
def upload_pdf():
    """Handle PDF file upload and analysis"""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename, 'pdf'):
        return jsonify({'error': 'Invalid file type. Please upload PDF file'}), 400
    
    try:
        # Extract failures
        failures = extract_pdf_failures(file)
        
        # Store in session
        session['current_pdf_failures'] = failures
        session['current_pdf_filename'] = file.filename
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'failures': failures,
            'total_failures': len([f for f in failures if not f.get('_no_failures', False)])
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing PDF: {str(e)}'}), 500


@app.route('/api/pdf/set-baseline', methods=['POST'])
def set_pdf_baseline():
    """Set current PDF report as baseline"""
    
    if 'current_pdf_failures' not in session:
        return jsonify({'error': 'No current report to set as baseline'}), 400
    
    baseline_storage['pdf'] = {
        'failures': session['current_pdf_failures'],
        'filename': session.get('current_pdf_filename', 'Unknown'),
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'message': 'Baseline set successfully',
        'baseline_filename': baseline_storage['pdf']['filename']
    })


@app.route('/api/pdf/baseline-info', methods=['GET'])
def pdf_baseline_info():
    """Get information about current PDF baseline"""
    
    if baseline_storage['pdf'] is None:
        return jsonify({'has_baseline': False})
    
    return jsonify({
        'has_baseline': True,
        'filename': baseline_storage['pdf']['filename'],
        'timestamp': baseline_storage['pdf']['timestamp'],
        'failure_count': len([f for f in baseline_storage['pdf']['failures'] 
                            if not f.get('_no_failures', False)])
    })


# ============================================================================
# ROUTES - AUTOMATION API REPORTS
# ============================================================================

@app.route('/api-reports')
def api_analyzer():
    """Automation API Report analyzer page"""
    return render_template('api_analyzer.html')


@app.route('/api/automation-api/upload', methods=['POST'])
def upload_api_report():
    """Handle Automation API XML file upload and analysis"""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename, 'xml'):
        return jsonify({'error': 'Invalid file type. Please upload XML file'}), 400
    
    try:
        # Extract failures from API report
        failures = extract_api_failures(file)
        
        # Store in session
        session['current_api_failures'] = failures
        session['current_api_filename'] = file.filename
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'failures': failures,
            'total_failures': len([f for f in failures if not f.get('_no_failures', False)]),
            'total_tests': failures[0].get('total_tests', 0) if failures else 0,
            'report_name': failures[0].get('report_name', 'Unknown') if failures else 'Unknown'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing API report: {str(e)}'}), 500


@app.route('/api/automation-api/set-baseline', methods=['POST'])
def set_api_baseline():
    """Set current API report as baseline"""
    
    if 'current_api_failures' not in session:
        return jsonify({'error': 'No current report to set as baseline'}), 400
    
    baseline_storage['api'] = {
        'failures': session['current_api_failures'],
        'filename': session.get('current_api_filename', 'Unknown'),
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'message': 'Baseline set successfully',
        'baseline_filename': baseline_storage['api']['filename']
    })


@app.route('/api/automation-api/compare', methods=['POST'])
def compare_api():
    """Compare current API report with baseline"""
    
    if 'current_api_failures' not in session:
        return jsonify({'error': 'No current report uploaded'}), 400
    
    if baseline_storage['api'] is None:
        return jsonify({'error': 'No baseline set. Please set a baseline first'}), 400
    
    try:
        current = session['current_api_failures']
        baseline = baseline_storage['api']['failures']
        
        comparison = compare_api_reports(current, baseline)
        
        return jsonify({
            'success': True,
            'comparison': comparison,
            'current_filename': session.get('current_api_filename', 'Current'),
            'baseline_filename': baseline_storage['api']['filename']
        })
        
    except Exception as e:
        return jsonify({'error': f'Error comparing reports: {str(e)}'}), 500


@app.route('/api/automation-api/baseline-info', methods=['GET'])
def api_baseline_info():
    """Get information about current API baseline"""
    
    if baseline_storage['api'] is None:
        return jsonify({'has_baseline': False})
    
    return jsonify({
        'has_baseline': True,
        'filename': baseline_storage['api']['filename'],
        'timestamp': baseline_storage['api']['timestamp'],
        'failure_count': len([f for f in baseline_storage['api']['failures'] 
                            if not f.get('_no_failures', False)])
    })


# ============================================================================
# UTILITY ROUTES
# ============================================================================

@app.route('/api/clear-session', methods=['POST'])
def clear_session():
    """Clear session data"""
    session.clear()
    return jsonify({'success': True, 'message': 'Session cleared'})


@app.route('/api/clear-baseline/<report_type>', methods=['POST'])
def clear_baseline(report_type):
    """Clear baseline for specific report type"""
    
    if report_type not in ['xml', 'pdf', 'api']:
        return jsonify({'error': 'Invalid report type'}), 400
    
    baseline_storage[report_type] = None
    
    return jsonify({
        'success': True,
        'message': f'{report_type.upper()} baseline cleared'
    })


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return jsonify({'error': 'File too large. Maximum size is 50MB'}), 413


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)