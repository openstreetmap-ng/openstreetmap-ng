# Admin User Management Interface - Implementation Progress

## Feature Overview
Implement a comprehensive admin interface for managing individual user accounts, providing administrators with complete control over user properties including display name, email, password, roles, and the ability to impersonate users. The interface follows Bootstrap 5 patterns with SCSS styling and TypeScript-powered standard forms for seamless data submission without page reloads.

## Requirements Summary
- Admin-only access with role_administrator requirement
- User loaded by ID in URL (not volatile display name)
- Editable fields: display name, email (with verification toggle), password, roles
- Read-only view of connected OAuth accounts
- Link to user-specific audit logs
- "Login as user" functionality for admin impersonation
- Standard form submission without page reload
- Role change confirmations via browser alerts
- No new localization strings (reuse existing where possible)
- Native feel matching existing settings panels

## Architecture Analysis

### Patterns Found
- **Settings Structure**: Settings pages extend `app/views/settings/_base.html.jinja` with consistent navigation (@app/views/settings/security.html.jinja)
- **Form Handling**: Standard forms use `configureStandardForm` with API endpoints returning JSON feedback (@app/views/lib/standard-form.ts)
- **Authentication**: Role-based access via `web_user('role_administrator')` decorator (@app/controllers/web_settings_users.py)
- **User Management**: Existing user list at `/settings/users` with pagination and filtering (@app/controllers/settings_users.py)
- **Content Headers**: User info displayed with avatar in headers like reports/diary pages (@app/views/reports/show.html.jinja:29-37)
- **Connected Accounts UI**: Table-based display with service icons (@app/views/settings/connections.html.jinja:10-42)

### Integration Strategy
The feature will integrate as a new route `/settings/users/{id}` extending the existing user management system. It will:
- Follow the settings page layout pattern with navigation sidebar
- Use standard forms for all data modifications
- Leverage existing user service methods where possible
- Connect to the audit system for user-specific logs
- Implement session manipulation for "login as" functionality

### Dependencies
- User model and roles system (@app/models/db/user.py)
- Standard form library (@app/views/lib/standard-form.ts)
- Auth context for session management (@app/lib/auth_context.py)
- Audit query system (@app/queries/audit_query.py)
- Connected accounts queries (@app/queries/connected_account_query.py)
- Password hashing utilities (@app/lib/password_hash.py)

### Risks & Considerations
- **Security**: "Login as" feature requires careful session handling to prevent security issues
- **Validation**: Email changes without verification need special handling
- **Audit Trail**: All admin actions must be properly logged
- **Role Changes**: Must handle edge cases like admin removing their own admin role
- **Session Management**: Consider impact on active user sessions when changing credentials

## Implementation Plan

### Phase 1: Backend Routes and Core Services - PENDING

**Objectives:**
- Create API endpoint for fetching user details
- Implement service methods for admin user modifications
- Add audit logging for all admin actions
- Create "login as user" functionality

**Approach:**
- Create `app/controllers/settings_user_edit.py` for page rendering
- Create `app/controllers/web_settings_user_edit.py` for API endpoints
- Extend `app/services/user_service.py` with admin modification methods
- Add new audit event types for admin actions
- Implement session replacement logic for impersonation

**Success Criteria:**
- GET `/settings/users/{id}` returns user edit page (admin only)
- API endpoints functional for all user modifications
- Audit events properly logged for each action
- "Login as" creates new session and redirects to homepage

### Phase 2: Frontend Template and Layout - PENDING

**Objectives:**
- Create user edit page with Bootstrap 5 layout
- Display user header with avatar and basic info
- Structure form sections for different user properties
- Add navigation and breadcrumbs

**Approach:**
- Create `app/views/settings/users/edit.html.jinja` extending settings base
- Implement content header similar to reports/diary pages
- Organize form fields in logical sections
- Add link to user-specific audit logs
- Style with Bootstrap classes following existing patterns

**Success Criteria:**
- Page renders with correct user information
- Layout matches existing settings pages
- All form elements properly structured
- Responsive design works on mobile/desktop

### Phase 3: Form Implementation with TypeScript - PENDING

**Objectives:**
- Configure standard forms for each editable section
- Implement role change confirmation dialogs
- Add real-time validation feedback
- Handle success/error responses

**Approach:**
- Create `app/views/settings/users/edit.ts` for form logic
- Use `configureStandardForm` for each form section
- Add confirmation dialogs for sensitive actions
- Implement client-side validation where appropriate
- Handle API responses with appropriate user feedback

**Success Criteria:**
- Forms submit without page reload
- Validation feedback appears inline
- Role changes show confirmation dialog
- Success/error messages display correctly

### Phase 4: Connected Accounts Display - PENDING

**Objectives:**
- Query and display user's connected OAuth accounts
- Create read-only table matching connections page style
- Show provider icons and connection status
- Add relevant metadata (connection date, etc.)

**Approach:**
- Query connected accounts via `ConnectedAccountQuery`
- Create partial template for account display
- Reuse styling from connections page
- Display only connected providers (no action buttons)

**Success Criteria:**
- Connected accounts display correctly
- Icons and styling match existing connections page
- No modification actions available (read-only)
- Displays connection timestamps

### Phase 5: Login As User Implementation - PENDING

**Objectives:**
- Implement secure session replacement
- Create new session for target user
- Redirect admin to homepage as impersonated user
- Log appropriate audit events

**Approach:**
- Add "Login as user" button in page header
- Create dedicated API endpoint for impersonation
- Replace current session with new user session
- Audit both logout and login events
- Clear admin session and create user session

**Success Criteria:**
- Admin can successfully impersonate user
- Session properly replaced (not stacked)
- Audit trail shows impersonation event
- Admin must re-authenticate to regain admin access

### Phase 6: Styling and Polish - PENDING

**Objectives:**
- Apply consistent SCSS styling
- Ensure responsive behavior
- Add loading states and transitions
- Polish UI interactions

**Approach:**
- Create `app/views/settings/users/edit.scss` 
- Match existing settings panel styles
- Add hover states and transitions
- Ensure mobile responsiveness
- Test with various data states

**Success Criteria:**
- Visual consistency with existing settings pages
- Smooth transitions and loading states
- Responsive on all screen sizes
- Accessible keyboard navigation

## Technical Decisions Log

### Form Structure
**Decision**: Use separate forms for each section (password, email, roles) rather than one large form
**Reasoning**: Allows independent validation and submission, reduces complexity, matches existing patterns in settings pages

### Session Management for Impersonation
**Decision**: Replace session entirely rather than stack/nest sessions
**Reasoning**: Simpler implementation, clearer security model, forces admin to re-authenticate for admin access

### Role Change Confirmations
**Decision**: Use native browser `confirm()` for role change warnings
**Reasoning**: Simple, accessible, doesn't require additional UI libraries, appropriate for admin interface

### No New Localization
**Decision**: Hard-code English strings for admin-only features, reuse existing translations where applicable
**Reasoning**: Reduces translation burden on community, admin interface doesn't need localization, follows project guidance

### Audit Integration
**Decision**: Link to filtered audit page rather than embed audit log
**Reasoning**: Reuses existing audit interface, keeps user edit page focused, maintains separation of concerns

### Password Change Method
**Decision**: Admin sets new password directly without knowing old password
**Reasoning**: Administrative override capability, matches expected admin permissions, simpler than password reset flow