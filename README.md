irc2slack maintains a connection to an IRC server and joins specified channels.  Whenever a new message appears in one of the monitored channels, irc2slack posts the message to the corresponding [Slack](https://slack.com/) channel using Slack's incoming webhook.  Using an outgoing webhook if configured in Slack, whenever a new message appears in one of the Slack channels for which the outgoing webhook is configured, irc2slack posts the message in the corresponding IRC channel.

The bot talks plain-text HTTP.  Get an SSL/TLS certificate for your server's host name.  Make irc2slack bind to loopback (see listen\_addr in irc2slack.conf) and use a snippet like this in [stunnel](https://www.stunnel.org/)'s configuration file to set up an HTTPS port:

```dosini
[bothttps]
accept  = 4433
connect = 8080
```

Configure https://_your-server-hostname_:4433/ in one or more outgoing webhooks in Slack.  Configure irc2slack.conf with the tokens that Slack generated for the outgoing webhooks.  That is how irc2slack authenticates Slack).  Create an incoming webhook in Slack and configure irc2slack.conf with it.
