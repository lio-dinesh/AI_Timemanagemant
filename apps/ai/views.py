import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from apps.ai.models import AIInsight, InsightType, InsightStatus
from apps.ai.services.scheduler import SchedulingOptimizer
from apps.ai.services.predictor import ProductivityPredictor
from apps.ai.services.anomaly import AnomalyDetector
from apps.ai.services.recommender import RecommenderService
from apps.ai.services.nlp import NLPCommandService
from apps.ai.services.nlp.evaluator import NLPEvaluator


@login_required
def insights_dashboard(request):
    insights = AIInsight.objects.filter(user=request.user, status=InsightStatus.ACTIVE).order_by('-generated_at')
    return render(request, 'ai/insights.html', {'insights': insights})


@login_required
@require_POST
def apply_insight(request, pk):
    try:
        event = SchedulingOptimizer.apply_schedule_recommendation(pk, request.user)
        messages.success(request, f"Applied AI suggestion: '{event.title}' added to calendar.")
    except Exception as e:
        messages.error(request, f"Could not apply suggestion: {str(e)}")
    return redirect('ai_insights')


@login_required
@require_POST
def dismiss_insight(request, pk):
    insight = get_object_or_404(AIInsight, pk=pk, user=request.user)
    insight.dismiss()
    if request.headers.get('HX-Request'):
        return HttpResponse("")
    messages.info(request, "Recommendation dismissed.")
    return redirect('ai_insights')


@login_required
@require_POST
def trigger_optimizer(request):
    SchedulingOptimizer.optimize_schedule_for_user(request.user)
    RecommenderService.generate_recommendations(request.user)
    AnomalyDetector.detect_user_anomalies(request.user)
    messages.success(request, "AI optimization and analysis complete. New insights generated!")
    return redirect('ai_insights')


@login_required
@require_POST
def nlp_command_prompt(request):
    command = request.POST.get('command') or ''
    conversation_id = request.POST.get('conversation_id') or None
    source = request.POST.get('source') or 'TEXT'

    if not command:
        if request.headers.get('HX-Request'):
            return HttpResponse("<div class='alert alert-warning py-1 small'>Please enter a command.</div>")
        return redirect('user_dashboard')

    result = NLPCommandService.parse_and_execute(
        command_text=command,
        user=request.user,
        conversation_id=conversation_id,
        source=source
    )

    if request.headers.get('HX-Request'):
        alert_class = "alert-success" if result.get('success') else "alert-warning"
        msg = result.get('message', '').replace('\n', '<br>')
        html = f"<div class='alert {alert_class} py-2 mb-2'><strong>{result.get('intent')}:</strong> {msg}"

        if result.get('requires_confirmation') and result.get('preview'):
            prev = result['preview']
            token = prev.get('confirm_token', '')
            cid = result.get('conversation_id', '')
            html += f"""
            <div class='mt-2 pt-2 border-top'>
                <button type='button' class='btn btn-sm btn-danger me-2' onclick="confirmNlpAction('{token}', '{cid}')">Confirm Action</button>
                <button type='button' class='btn btn-sm btn-outline-secondary' onclick="cancelNlpAction('{cid}')">Cancel</button>
            </div>
            """

        if result.get('candidates'):
            html += "<div class='mt-2 d-flex flex-wrap gap-1'>"
            for i, cand in enumerate(result['candidates']):
                c_title = cand.get('title', '')
                html += f"<button type='button' class='btn btn-sm btn-outline-primary' onclick=\"selectNlpCandidate({i+1}, '{result.get('conversation_id', '')}')\">{i+1}. {c_title}</button>"
            html += "</div>"

        html += "</div>"
        return HttpResponse(html)

    if result.get('success'):
        messages.success(request, result.get('message'))
    else:
        messages.warning(request, result.get('message'))
    return redirect('user_dashboard')


# -------------------------------------------------------------
# REST API Endpoints
# -------------------------------------------------------------

@login_required
def api_insights_list(request):
    insights = AIInsight.objects.filter(user=request.user, status=InsightStatus.ACTIVE)
    data = [{
        'id': i.id,
        'type': i.insight_type,
        'confidence': i.confidence,
        'payload': i.payload,
        'generated_at': i.generated_at.isoformat()
    } for i in insights]
    return JsonResponse({'status': 'success', 'insights': data})


@login_required
@require_POST
def api_nlp_command(request):
    try:
        data = json.loads(request.body) if request.body else {}
        command = data.get('command', '')
        conversation_id = data.get('conversation_id')
        source = data.get('source', 'TEXT')

        result = NLPCommandService.parse_and_execute(
            command_text=command,
            user=request.user,
            conversation_id=conversation_id,
            source=source
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@require_POST
def api_nlp_confirm(request):
    try:
        data = json.loads(request.body) if request.body else {}
        token = data.get('token')
        conversation_id = data.get('conversation_id')

        # Route confirmation through NLPCommandService with "confirm"
        result = NLPCommandService.parse_and_execute(
            command_text="confirm",
            user=request.user,
            conversation_id=conversation_id
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@require_POST
def api_nlp_cancel(request):
    try:
        data = json.loads(request.body) if request.body else {}
        conversation_id = data.get('conversation_id')

        result = NLPCommandService.parse_and_execute(
            command_text="cancel",
            user=request.user,
            conversation_id=conversation_id
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def api_nlp_evaluate(request):
    try:
        metrics = NLPEvaluator.evaluate(request.user)
        return JsonResponse({'status': 'success', 'metrics': metrics})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
