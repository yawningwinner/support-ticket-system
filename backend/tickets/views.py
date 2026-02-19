from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Ticket
from .serializers import TicketSerializer, ClassifyRequestSerializer
from .llm_service import classify_ticket


@api_view(['GET', 'POST'])
def ticket_list_create(request):
    if request.method == 'GET':
        qs = Ticket.objects.all().order_by('-created_at')
        category = request.query_params.get('category')
        priority = request.query_params.get('priority')
        status_filter = request.query_params.get('status')
        search = request.query_params.get('search', '').strip()
        if category:
            qs = qs.filter(category=category)
        if priority:
            qs = qs.filter(priority=priority)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        serializer = TicketSerializer(qs, many=True)
        return Response(serializer.data)
    elif request.method == 'POST':
        serializer = TicketSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
def ticket_detail(request, pk):
    try:
        ticket = Ticket.objects.get(pk=pk)
    except Ticket.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = TicketSerializer(ticket)
        return Response(serializer.data)
    elif request.method == 'PATCH':
        serializer = TicketSerializer(ticket, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def ticket_stats(request):
    """Aggregated stats using DB-level aggregation only."""
    total = Ticket.objects.count()
    open_count = Ticket.objects.filter(status='open').count()
    num_days = Ticket.objects.annotate(
        day=TruncDate('created_at')
    ).values('day').distinct().count()
    avg_per_day = round(total / num_days, 1) if num_days else 0.0

    priority_breakdown = dict(
        Ticket.objects.values('priority').annotate(cnt=Count('id')).values_list('priority', 'cnt')
    )
    for p in ['low', 'medium', 'high', 'critical']:
        priority_breakdown.setdefault(p, 0)

    category_breakdown = dict(
        Ticket.objects.values('category').annotate(cnt=Count('id')).values_list('category', 'cnt')
    )
    for c in ['billing', 'technical', 'account', 'general']:
        category_breakdown.setdefault(c, 0)

    return Response({
        'total_tickets': total,
        'open_tickets': open_count,
        'avg_tickets_per_day': avg_per_day,
        'priority_breakdown': priority_breakdown,
        'category_breakdown': category_breakdown,
    })


@api_view(['POST'])
def ticket_classify(request):
    serializer = ClassifyRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    result = classify_ticket(serializer.validated_data['description'])
    if result is None:
        return Response(
            {'suggested_category': None, 'suggested_priority': None},
            status=status.HTTP_200_OK,
        )
    return Response(result)
