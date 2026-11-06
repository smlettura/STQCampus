#!/bin/sh
# Crea las tareas diaria (06:00) y mensual (día 1, 07:00) en EventBridge Scheduler. Cada una ejecuta en la instancia,
# mediante Systems Manager Run Command, el comando de Django «ejecutar_tarea». No se expone ningún punto HTTP.
set -e
INSTANCIA="${INSTANCIA:?Defina INSTANCIA (id de la EC2)}"
ROL="${ROL:?Defina ROL (ARN del rol que permite ssm:SendCommand sobre la instancia)}"
for TAREA in diaria mensual; do
  if [ "$TAREA" = diaria ]; then CRON="cron(0 6 * * ? *)"; else CRON="cron(0 7 1 * ? *)"; fi
  aws scheduler create-schedule --name "stq-tarea-$TAREA" \
    --schedule-expression "$CRON" --schedule-expression-timezone "America/Santiago" \
    --flexible-time-window Mode=OFF \
    --target "{\"Arn\":\"arn:aws:scheduler:::aws-sdk:ssm:sendCommand\",\"RoleArn\":\"$ROL\",
      \"Input\":\"{\\\"DocumentName\\\":\\\"AWS-RunShellScript\\\",\\\"InstanceIds\\\":[\\\"$INSTANCIA\\\"],
      \\\"Parameters\\\":{\\\"commands\\\":[\\\"docker exec stq-app python manage.py ejecutar_tarea $TAREA\\\"]}}\"}"
done
