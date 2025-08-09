# Report Confirmation Email Improvement - Implementation Progress

## Feature Overview
Enhance report confirmation emails to provide clear, context-aware information about what was reported, replacing the confusing generic "For your reference, you wrote (preview)" text with specific details and links to reported content.

## Requirements Summary
- Context-specific confirmation emails based on report type
- Direct links to reported content where applicable
- Fully localizable with reuse of existing strings
- Professional UX with clear communication
- No category display in emails
- Use "changeset 123" format (not "#123")
- Simplify redundant localization strings using interpolation

## Architecture Analysis

### Project Structure
- **Email Templates**: @app/views/email/ - Jinja2 templates with base template inheritance
- **Report System**: @app/services/report_service.py - Service layer handling report creation and email sending
- **Localization**: Dual system with @config/locale/en.yaml (legacy, read-only) and @config/locale/extra_en.yaml (new, editable)
- **Models**: @app/models/db/report.py and @app/models/db/report_comment.py define data structures

### Design Patterns
- **Template Inheritance**: Email templates extend @app/views/email/_base.html.jinja
- **Service Layer Pattern**: ReportService encapsulates business logic
- **Rich Text Support**: Comments include `body_rich` field with resolved rich text
- **Localization Pattern**: `t()` function with dot notation keys and interpolation support

### Conventions
- **Simplification Principle**: NG version prefers single strings for commonly reused words
- **Localization Reuse**: Use generic patterns with interpolation where possible
- **Object Naming**: Direct object names without "#" prefix (e.g., "changeset 123")

### Existing Object Names in Localization
From @config/locale/extra_en.yaml:
- `changeset.count_one: "changeset"` (line 42)
- `diary.entry.count_one: "diary entry"` (line 68)
- `note.count_one: "note"` (line 52)
- `trace.count_one: "trace"` (line 60)
- Message: Need to add or use from en.yaml

### Templates Using Report Strings
- @app/views/partial/changeset.html.jinja - Uses `report.report_changeset`
- @app/views/traces/details.html.jinja - Uses `report.report_trace`
- @app/views/partial/note.html.jinja - Uses `report.report_note`
- @app/views/diary/_entry.html.jinja - Uses `report.report_diary`
- @app/views/messages/index.html.jinja - Uses `report.report_message`

## Implementation Plan

### Phase 1: Simplify Report Localization Strings - COMPLETED

**Objectives:**
- Remove redundant report_* strings
- Create generic pattern using interpolation
- Keep special cases that don't fit the pattern

**Approach:**
1. Replace individual report strings with generic pattern
2. Add missing object names if needed
3. Keep special strings for user profile and account support

**Implementation:**
- Modified: @config/locale/extra_en.yaml
  - Removed redundant strings: `report_changeset`, `report_diary`, `report_message`, `report_note`, `report_trace`, `report_user`, `report_application`
  - Added generic pattern: `report_object: "Report {{object}}"`
  - Kept special case: `report_problem: Report a problem`
  - Key decision: Using `report_object` as the key name for clarity

### Phase 2: Update HTML Templates - COMPLETED

**Objectives:**
- Update all templates to use new generic pattern
- Pass object names as interpolation parameters
- Maintain consistent UX

**Implementation:**
- Modified: @app/views/partial/changeset.html.jinja:92
  - Changed to: `t('report.report_object', object=t('changeset.count_one'))`
- Modified: @app/views/traces/details.html.jinja:41
  - Changed to: `t('report.report_object', object=t('trace.count_one'))`
- Modified: @app/views/partial/note.html.jinja:64,72
  - Changed to: `t('report.report_object', object=t('note.count_one'))`
- Modified: @app/views/diary/_entry.html.jinja:156
  - Changed to: `t('report.report_object', object=t('diary.entry.count_one'))`
- Modified: @app/views/messages/index.html.jinja:100
  - Changed to: `t('report.report_object', object=t('activerecord.models.message'))`
- Modified: @app/views/user/profile/profile.html.jinja:180
  - Changed to: `t('report.report_object', object=t('activerecord.models.user'))`
- Modified: @app/views/settings/applications/_application-entry.html.jinja:116
  - Changed to: `t('report.report_object', object=t('oauth2_authorized_applications.index.application'))`

**Notes:**
- Used existing localization keys from en.yaml for object names
- Message uses `activerecord.models.message` (line 67 in en.yaml)
- User uses `activerecord.models.user` (line 86 in en.yaml)
- Application uses `oauth2_authorized_applications.index.application` (line 2824 in en.yaml)

### Phase 3: Email Confirmation Context - PENDING

**Objectives:**
- Add context-aware strings for email confirmations
- Create clear messaging about what was reported
- Support links to reported content

**Approach:**
1. Add email-specific localization strings
2. Use same object name patterns for consistency
3. Create composable strings for flexibility

**Files to Modify:**
- config/locale/extra_en.yaml

**Email Localization Structure:**
```yaml
report:
  email_confirmation:
    # Existing (lines 526-529)...
    # New additions:
    you_reported: "You reported {{object}}"
    you_reported_with_id: "You reported {{object}} {{id}}"
    
    # For complex cases that need special formatting:
    reported_user_profile: "You reported {{user}}'s profile"
    reported_account_problem: "You reported a problem with your account"
    reported_oauth_app: "You reported OAuth2 application {{name}}"
    
    # Supporting text:
    by_user: "by {{user}}"
    your_message: "Your message:"
```

### Phase 4: Service Layer Enhancement - PENDING

**Objectives:**
- Load minimal context for email display
- Pass object names to template
- Handle missing data gracefully

**Approach:**
1. In ReportService.create_report(), after line 100
2. Add object_name to template_data based on action
3. For some actions, query additional context (e.g., OAuth app name)

**Files to Modify:**
- app/services/report_service.py

**Service Logic:**
```python
# After line 100 (comment resolution):
template_data = {'comment': comment}

# Map action to object name key
object_name_map = {
    'user_changeset': 'changeset.count_one',
    'user_diary': 'diary.entry.count_one', 
    'user_note': 'note.count_one',
    'user_trace': 'trace.count_one',
    'user_message': 'message.count_one',
}

if comment['action'] in object_name_map:
    template_data['object_name_key'] = object_name_map[comment['action']]
elif comment['action'] == 'user_oauth2_application':
    # Query app name if needed
    pass
# ... handle other special cases

await EmailService.schedule(
    # ... existing params ...
    template_data=template_data,
)
```

### Phase 5: Email Template Implementation - PENDING

**Objectives:**
- Replace generic preview with specific context
- Include links to reported content
- Use simplified localization patterns

**Approach:**
1. Restructure report-confirm.html.jinja
2. Use object interpolation pattern
3. Build absolute URLs for links

**Files to Modify:**
- app/views/email/report-confirm.html.jinja

**Template Structure:**
```jinja
{% extends 'email/_base' %}
{% block body %}
<p>{{ t('notifications.hello_user', user=user.display_name) }}</p>
<p>{{ t('report.email_confirmation.thank_you_our_team_will_review') }}</p>

<p><strong>
{% if comment.action == 'user_changeset' %}
    {{ t('report.email_confirmation.you_reported_with_id', 
        object=t('changeset.count_one'), 
        id='<a href="' + APP_URL + '/changeset/' + comment.action_id|string + '">' + comment.action_id|string + '</a>') | safe }}
{% elif comment.action == 'user_diary' %}
    {{ t('report.email_confirmation.you_reported_with_id',
        object=t('diary.entry.count_one'),
        id='<a href="' + APP_URL + '/diary/' + comment.action_id|string + '">' + comment.action_id|string + '</a>') | safe }}
{% elif comment.action == 'user_note' %}
    {{ t('report.email_confirmation.you_reported_with_id',
        object=t('note.count_one'),
        id='<a href="' + APP_URL + '/note/' + comment.action_id|string + '">' + comment.action_id|string + '</a>') | safe }}
{% elif comment.action == 'user_trace' %}
    {{ t('report.email_confirmation.you_reported_with_id',
        object='GPS ' + t('trace.count_one'),
        id='<a href="' + APP_URL + '/trace/' + comment.action_id|string + '">' + comment.action_id|string + '</a>') | safe }}
{% elif comment.action == 'user_message' %}
    {{ t('report.email_confirmation.you_reported',
        object=t('message.count_one')) }}
{% elif comment.action == 'user_profile' %}
    {{ t('report.email_confirmation.reported_user_profile',
        user='<a href="' + APP_URL + '/user/' + reported_user.display_name + '">' + reported_user.display_name + '</a>') | safe }}
{% elif comment.action == 'user_account' %}
    {{ t('report.email_confirmation.reported_account_problem') }}
{% elif comment.action == 'user_oauth2_application' %}
    {{ t('report.email_confirmation.reported_oauth_app',
        name=oauth_app_name|default(comment.action_id)) }}
{% endif %}
</strong></p>

{% if comment.body %}
<p><i>{{ t('report.email_confirmation.your_message') }}</i></p>
<table style="width: 100%; margin: 1em 0; background: #eee">
    <tr>
        <td style="width: 50px; vertical-align: top">
            <div style="margin: 1em">
                <a href="{{ APP_URL }}/user-id/{{ comment.user_id }}">
                    <img src="{{ APP_URL }}{{ user_avatar_url(comment.user) }}" 
                         alt="{{ t('alt.profile_picture') }}"
                         width="50" height="50" 
                         style="background: #fff; border-radius: 50%">
                </a>
            </div>
        </td>
        <td style="vertical-align: top">
            <div style="margin: 1em 1em 1em 0;">{{ comment.body_rich | safe }}</div>
        </td>
    </tr>
</table>
{% endif %}
{% endblock %}
```

### Phase 6: Testing & Validation - PENDING

**Objectives:**
- Verify simplified localization works correctly
- Test all report types with new pattern
- Validate email rendering

**Approach:**
1. Test generic pattern with all applicable report types
2. Verify special cases still work
3. Check interpolation in both UI and emails
4. Test with missing data scenarios

**Test Scenarios:**
- Generic pattern: changeset, diary, note, trace, message
- Special cases: user profile, account problem, OAuth app
- Missing action_id handling
- Localization fallbacks
- Email HTML rendering

## Technical Decisions Log

### Simplification Strategy
- **Decision**: Use generic `Report {{object}}` pattern
- **Rationale**: Reduces 5+ strings to 1, follows NG simplification principle
- **Trade-off**: Slightly more complex template logic for better maintainability

### Object Name Reuse
- **Decision**: Reuse existing count_one strings for object names
- **Rationale**: Avoids duplication, maintains consistency
- **Example**: `changeset.count_one` instead of new `changeset.name`

### Special Cases
- **Decision**: Keep specific strings for user, application, and account reports
- **Rationale**: These don't fit the generic pattern cleanly
- **Implementation**: Separate localization keys for these cases

### GPS Trace Handling
- **Decision**: Concatenate "GPS " + trace object name in template
- **Rationale**: Maintains consistency with existing UI while using generic pattern
- **Alternative**: Could add specific "GPS trace" string if preferred

## Integration Points

### Data Flow
1. ReportService creates report and comment
2. Service determines object name key based on action
3. Email template receives comment and object context
4. Template uses generic pattern with interpolation
5. Localization system resolves final strings

### Dependencies
- Existing object name strings in extra_en.yaml
- Translation system with interpolation support
- EmailService for delivery
- APP_URL for absolute links

## Success Criteria

The implementation is complete when:
- ✅ Redundant report_* strings removed from localization
- ✅ Generic pattern `Report {{object}}` implemented
- ✅ All UI templates updated to use new pattern
- ✅ Email shows specific context with proper object names
- ✅ Links work correctly (changeset 123 format)
- ✅ Special cases handled appropriately
- ✅ No duplicate strings in localization files
- ✅ Code follows NG simplification principles