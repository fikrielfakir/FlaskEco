# Overview

EcoQuality is a comprehensive quality management system specifically designed for ceramic tile manufacturing facilities. The application provides end-to-end production tracking, quality control testing, energy monitoring, and waste management capabilities. Built with Flask and SQLAlchemy, the system focuses on ISO compliance (particularly ISO 13006 for ceramic tiles), environmental sustainability, and production efficiency. The application supports role-based access for operators, supervisors, and quality technicians to manage ceramic production workflows from raw materials to finished products.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap 5 for responsive UI
- **Styling**: Custom CSS with Bootstrap dark theme integration
- **JavaScript**: Vanilla JavaScript for form validation, tooltips, and interactive features
- **Responsive Design**: Mobile-first approach with responsive grid layouts
- **Navigation**: Role-based navigation system with contextual menu items

## Backend Architecture
- **Framework**: Flask web framework with modular route organization
- **ORM**: SQLAlchemy with declarative base for database modeling
- **Authentication**: Flask-Login for session management and user authentication
- **Database**: SQLite for development with PostgreSQL support for production
- **Security**: Password hashing with Werkzeug, CSRF protection, and session management

## Database Design
- **User Management**: Role-based user system (Operator, Supervisor, Technician)
- **Production Tracking**: Batch management with kiln operations and status tracking
- **Quality Control**: Test results linked to production batches with ISO compliance scoring
- **Resource Management**: Energy consumption tracking and waste management records
- **Materials**: Raw materials inventory with supplier and quality certification tracking

## Authentication & Authorization
- **Session-based Authentication**: Flask-Login with secure session management
- **Role-based Access Control**: Different access levels for operators, supervisors, and technicians
- **Password Security**: Werkzeug password hashing with secure defaults
- **Login Protection**: Required authentication decorators for protected routes

## Data Models
- **Production Flow**: ProductionBatch → QualityTest relationship for traceability
- **User Relationships**: Users linked to supervised batches and performed tests
- **Resource Tracking**: Separate models for energy consumption and waste records
- **ISO Standards**: Dedicated model for quality standards and compliance requirements

# External Dependencies

## Core Framework Dependencies
- **Flask**: Web application framework
- **Flask-SQLAlchemy**: Database ORM integration
- **Flask-Login**: User session management
- **Werkzeug**: Password hashing and security utilities

## Frontend Dependencies
- **Bootstrap 5**: UI framework with dark theme support
- **Font Awesome**: Icon library for UI elements
- **CDN Resources**: Bootstrap and Font Awesome served via CDN

## Database Systems
- **SQLite**: Default development database
- **PostgreSQL**: Production database support (configurable via DATABASE_URL)
- **Connection Pooling**: Configured for production with pool recycling and pre-ping

## Production Infrastructure
- **ProxyFix**: Werkzeug middleware for reverse proxy support
- **Environment Configuration**: Environment variable support for secrets and database URLs
- **Logging**: Python logging configured for debugging and monitoring

## Data Initialization
- **Database Seeding**: Automated sample data creation for demonstration
- **ISO Standards**: Pre-configured quality standards and test parameters
- **User Roles**: Default user accounts with different permission levels