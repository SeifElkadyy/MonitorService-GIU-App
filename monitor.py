import os
import json
import hashlib
import requests
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

class GitHubPortalMonitor:
    def __init__(self):
        # Get credentials from environment variables (GitHub secrets)
        self.username = os.getenv('GIU_USERNAME')
        self.password = os.getenv('GIU_PASSWORD')
        self.email = os.getenv('YOUR_EMAIL')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.api_url = "https://portalapp-hazel.vercel.app"
        
        # Storage files (GitHub repo will store these)
        self.data_file = "previous_data.json"
        
    def log(self, message):
        """Simple logging"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def make_api_request(self, endpoint, params=None):
        """Make API request with retry"""
        base_params = {"username": self.username, "password": self.password}
        if params:
            base_params.update(params)
        
        for attempt in range(3):
            try:
                self.log(f"📡 Fetching {endpoint}...")
                response = requests.post(
                    f"{self.api_url}/{endpoint}",
                    json=base_params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        return result.get('data', {})
                
                self.log(f"❌ API error for {endpoint}: {response.status_code}")
                
            except Exception as e:
                self.log(f"❌ Request error for {endpoint}: {str(e)}")
                
            if attempt < 2:
                time.sleep(2)
        
        return None
    
    def fetch_summary_data(self):
        """Fetch summary data to get courses and years"""
        self.log("🔍 Fetching summary data...")
        
        summary = {}
        endpoints = ['grades', 'attendance', 'transcript']
        
        for endpoint in endpoints:
            data = self.make_api_request(endpoint)
            summary[endpoint] = data
            time.sleep(1)
        
        return summary
    
    def extract_courses_and_years(self, summary):
        """Extract available courses and years"""
        courses = set()
        years = []
        
        # Extract courses from grades and attendance
        for data_type in ['grades', 'attendance']:
            if summary.get(data_type) and 'available_courses' in summary[data_type]:
                for course in summary[data_type]['available_courses']:
                    if isinstance(course, dict) and 'code' in course:
                        courses.add(course['code'])
        
        # Extract years from transcript (filter 2022+)
        if summary.get('transcript') and 'available_years' in summary['transcript']:
            for year_info in summary['transcript']['available_years']:
                if isinstance(year_info, dict):
                    year_text = year_info.get('text', '')
                    year_value = year_info.get('value', '')
                    # Only include 2022 and later
                    if any(y in year_text for y in ['2022', '2023', '2024', '2025']):
                        years.append({'text': year_text, 'value': year_value})
        
        self.log(f"📚 Found {len(courses)} courses: {list(courses)[:5]}...")
        self.log(f"📅 Found {len(years)} years: {[y['text'] for y in years]}")
        
        return list(courses), years
    
    def fetch_detailed_data(self, courses, years):
        """Fetch detailed data for all courses and years"""
        detailed_data = {
            'detailed_grades': {},
            'detailed_attendance': {},
            'detailed_transcripts': {},
            'summary': {}
        }
        
        # Fetch summary first
        summary = self.fetch_summary_data()
        detailed_data['summary'] = summary
        
        # Fetch detailed grades for each course
        self.log(f"📊 Fetching detailed grades for {len(courses)} courses...")
        for course_code in courses:
            try:
                course_grades = self.make_api_request('grades', {'course_code': course_code})
                if course_grades:
                    detailed_data['detailed_grades'][course_code] = course_grades
                    self.log(f"✅ Grades fetched for {course_code}")
                time.sleep(2)
            except Exception as e:
                self.log(f"❌ Error fetching grades for {course_code}: {e}")
        
        # Fetch detailed attendance for each course
        self.log(f"📅 Fetching detailed attendance for {len(courses)} courses...")
        for course_code in courses:
            try:
                course_attendance = self.make_api_request('attendance', {'course_code': course_code})
                if course_attendance:
                    detailed_data['detailed_attendance'][course_code] = course_attendance
                    self.log(f"✅ Attendance fetched for {course_code}")
                time.sleep(2)
            except Exception as e:
                self.log(f"❌ Error fetching attendance for {course_code}: {e}")
        
        # Fetch detailed transcripts for each year
        self.log(f"🎓 Fetching detailed transcripts for {len(years)} years...")
        for year_info in years:
            try:
                year_value = year_info['value']
                year_text = year_info['text']
                year_transcript = self.make_api_request('transcript', {'year_value': year_value})
                if year_transcript:
                    detailed_data['detailed_transcripts'][year_text] = year_transcript
                    self.log(f"✅ Transcript fetched for {year_text}")
                time.sleep(2)
            except Exception as e:
                self.log(f"❌ Error fetching transcript for {year_info['text']}: {e}")
        
        return detailed_data
    
    def load_previous_data(self):
        """Load previous data from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.log(f"❌ Error loading previous data: {e}")
        return None
    
    def save_current_data(self, data):
        """Save current data to file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.log("💾 Current data saved")
        except Exception as e:
            self.log(f"❌ Error saving data: {e}")
    
    def hash_data(self, data):
        """Create hash for comparison"""
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def detect_changes(self, old_data, new_data):
        """Detect all changes in detailed data"""
        changes = []
        
        if old_data is None:
            changes.append("🆕 Initial data fetch - monitoring started!")
            return changes
        
        # Check summary changes
        for data_type in ['grades', 'attendance', 'transcript']:
            old_summary = old_data.get('summary', {}).get(data_type, {})
            new_summary = new_data.get('summary', {}).get(data_type, {})
            
            if self.hash_data(old_summary) != self.hash_data(new_summary):
                changes.append(f"📊 {data_type.title()} summary updated")
        
        # Check detailed grades changes
        old_grades = old_data.get('detailed_grades', {})
        new_grades = new_data.get('detailed_grades', {})
        
        for course_code, course_data in new_grades.items():
            old_course_data = old_grades.get(course_code, {})
            
            if self.hash_data(old_course_data) != self.hash_data(course_data):
                # Detailed change detection for grades
                old_detailed = old_course_data.get('detailed_grades', [])
                new_detailed = course_data.get('detailed_grades', [])
                
                if len(new_detailed) > len(old_detailed):
                    changes.append(f"📝 {len(new_detailed) - len(old_detailed)} new grade entries for {course_code}")
                
                # Check midterm results
                old_midterms = old_course_data.get('midterm_results', [])
                new_midterms = course_data.get('midterm_results', [])
                
                if len(new_midterms) > len(old_midterms):
                    changes.append(f"🎯 New midterm results for {course_code}")
                
                if self.hash_data(old_midterms) != self.hash_data(new_midterms):
                    changes.append(f"📈 Grade changes detected for {course_code}")
        
        # Check detailed attendance changes
        old_attendance = old_data.get('detailed_attendance', {})
        new_attendance = new_data.get('detailed_attendance', {})
        
        for course_code, course_data in new_attendance.items():
            old_course_data = old_attendance.get(course_code, {})
            
            if self.hash_data(old_course_data) != self.hash_data(course_data):
                old_detailed = old_course_data.get('detailed_attendance', [])
                new_detailed = course_data.get('detailed_attendance', [])
                
                if len(new_detailed) > len(old_detailed):
                    changes.append(f"📅 {len(new_detailed) - len(old_detailed)} new attendance entries for {course_code}")
                
                # Check for warning changes
                old_warnings = old_course_data.get('warning_courses', [])
                new_warnings = course_data.get('warning_courses', [])
                
                if len(new_warnings) > len(old_warnings):
                    changes.append(f"⚠️ New attendance warnings for {course_code}")
        
        # Check transcript changes
        old_transcripts = old_data.get('detailed_transcripts', {})
        new_transcripts = new_data.get('detailed_transcripts', {})
        
        for year, year_data in new_transcripts.items():
            old_year_data = old_transcripts.get(year, {})
            
            if self.hash_data(old_year_data) != self.hash_data(year_data):
                # Check GPA changes
                old_gpa = old_year_data.get('gpa')
                new_gpa = year_data.get('gpa')
                
                if old_gpa != new_gpa:
                    changes.append(f"🎓 GPA updated for {year}: {old_gpa} → {new_gpa}")
                
                # Check course count
                old_courses = len(old_year_data.get('transcript_data', []))
                new_courses = len(year_data.get('transcript_data', []))
                
                if new_courses > old_courses:
                    changes.append(f"📚 {new_courses - old_courses} new courses in {year} transcript")
        
        return changes
    
    def send_email(self, changes):
        """Send detailed email notification"""
        if not changes:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = self.email
            msg['Subject'] = f"🎓 GIU Portal Updates - {len(changes)} Change(s) Detected"
            
            # Create detailed email body
            body = f"Hello!\n\n"
            body += f"📋 DETAILED GIU PORTAL MONITORING RESULTS\n"
            body += f"{'='*50}\n\n"
            body += f"Total Changes Detected: {len(changes)}\n\n"
            
            # Group changes by type
            grade_changes = [c for c in changes if any(word in c.lower() for word in ['grade', 'midterm'])]
            attendance_changes = [c for c in changes if any(word in c.lower() for word in ['attendance', 'warning'])]
            transcript_changes = [c for c in changes if any(word in c.lower() for word in ['transcript', 'gpa', 'course'])]
            other_changes = [c for c in changes if c not in grade_changes + attendance_changes + transcript_changes]
            
            if grade_changes:
                body += f"📊 GRADES CHANGES ({len(grade_changes)}):\n"
                for i, change in enumerate(grade_changes, 1):
                    body += f"  {i}. {change}\n"
                body += "\n"
            
            if attendance_changes:
                body += f"📅 ATTENDANCE CHANGES ({len(attendance_changes)}):\n"
                for i, change in enumerate(attendance_changes, 1):
                    body += f"  {i}. {change}\n"
                body += "\n"
            
            if transcript_changes:
                body += f"🎓 TRANSCRIPT CHANGES ({len(transcript_changes)}):\n"
                for i, change in enumerate(transcript_changes, 1):
                    body += f"  {i}. {change}\n"
                body += "\n"
            
            if other_changes:
                body += f"📋 OTHER CHANGES ({len(other_changes)}):\n"
                for i, change in enumerate(other_changes, 1):
                    body += f"  {i}. {change}\n"
                body += "\n"
            
            body += f"⏰ Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            body += f"🔗 Visit: https://portal.giu-uni.de\n"
            body += f"\n🤖 Automated GIU Portal Monitor (GitHub Actions)"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.email, self.email_password)
            server.send_message(msg)
            server.quit()
            
            self.log(f"✅ Email sent successfully with {len(changes)} changes")
            
        except Exception as e:
            self.log(f"❌ Failed to send email: {str(e)}")
    
    def run_monitoring(self):
        """Main monitoring function"""
        self.log("🚀 Starting GitHub Actions GIU Portal Monitor...")
        
        try:
            # Get summary data to extract courses and years
            summary = self.fetch_summary_data()
            courses, years = self.extract_courses_and_years(summary)
            
            if not courses:
                self.log("❌ No courses found - check credentials")
                return
            
            # Fetch all detailed data
            current_data = self.fetch_detailed_data(courses, years)
            
            # Load previous data for comparison
            previous_data = self.load_previous_data()
            
            # Detect changes
            changes = self.detect_changes(previous_data, current_data)
            
            # Send email if changes found
            if changes:
                self.log(f"📧 {len(changes)} changes detected - sending email...")
                self.send_email(changes)
            else:
                self.log("✅ No changes detected")
            
            # Save current data for next run
            self.save_current_data(current_data)
            
            self.log("🎯 Monitoring completed successfully!")
            
        except Exception as e:
            self.log(f"❌ Error in monitoring: {str(e)}")
            # Send error email
            self.send_email([f"❌ Monitoring error: {str(e)}"])

if __name__ == "__main__":
    monitor = GitHubPortalMonitor()
    monitor.run_monitoring()
