SELECT c.campaign_id,
       t.merchant_id,
       m.name,
       cm.message_type,
       c.customers_cap,
       c.title,
       c.description
FROM   triggers t,
       campaigns c,
       campaign_messages cm,
       campaign_triggers_assoc cta,
       merchants m
WHERE  t.customers_cap > 0
       AND t.frequency_in_hours > 0
       AND t.merchant_id = m.merchant_id
       AND t.id = cta.trigger_id
       AND cta.campaign_id = c.campaign_id
       AND cm.campaign_id = c.campaign_id
       AND cm.message_type = 'email'
       AND t.active;
