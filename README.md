# Ansible Dovecot Role

Based on the work of "practical-ansible", this role configures a Dovecot mailserver to work with
an MTA (such as exim or postfix).

The role installs Dovecot and configures them to act together as IMAP/SMTP mail server with
virtual database of mailboxes and domains provided by OpenLDAP. Uses Lets Encrypt to generate
certificates for communication.

## Requirements

You need to define `{{base_domain}}` to keep your passwords stored in password storage. Hostname of
your mail server will be configured as `mail.{{base_domain}}` unless you override variable
`{{mail_host}}`.

## Additional configuration

This Ansible role is not able to configure DNS for you. You will need to configure the DNS records.

## Role Variables

The email domain of this server, as seen by outside world:
``` yaml
    dovecot_domain: mail.example.org
```

Local hostname of server (what it calls itself):
``` yaml
    dovecot_host: '{{ hostname_fqdn }}'
```

Local addresses, on which the server will listen:
``` yaml
    dovecot_host_address: [ "192.168.2.1", "127.0.0.1", "::1" ]
```

Local networks (CIDR) that are trusted and so do not require auth:
``` yaml
    dovecot_trusted_networks: [ "192.168.2.0/28" ]
```

Directory in which the certificate for SSL transport is found:
``` yaml
    dovecot_dir_cert: '/etc/letsencrypt/live'
```

Directory in which incoming mail will be stored:
``` yaml
    dovecot_dir_storage: /srv/mail
```

Configuration directory for Dovecot itself:
``` yaml
    dovecot_dir: /etc/dovecot
```

Configuration directory for Dovecot itself (run-parts version):
``` yaml
    dovecot_dir_config: /etc/dovecot/conf.d
```

Domain administrator email address:
``` yaml
    dovecot_admin_address: 'postmaster@{{dovecot_domain}}'
```

Enable/Disable the Dovecot LDAP connector. If enabled, an LDAP server is also required:
``` yaml
    dovecot_ldap_enabled: no
```

Enable/Disable TLS communication (POP3S, IMAPS, etc):
``` yaml
    dovecot_ssl_enabled: yes
```

Database host, name and credentials for the Dovecot users database.
``` yaml
    dovecot_db_hostname: localhost
    dovecot_db_database: email
    dovecot_db_table: users
    dovecot_db_user: postman
    dovecot_db_password: "secrets-in-vault"
```

Configuration for the LMTP (local message transfer protocol, like SMTP
but tweaked for sockets based local delivery) daemon. This is how email
is normally delivered to Dovecot.  You almost certainly want this, and
the MTA delivering to Dovecot needs to know the socket pathname.
``` yaml
    dovecot_lmtp:
      socket: /var/run/dovecot/lmtp
```

Configuration for the Dovecot IMAP daemon. This is how client mail readers
get to read mail delivered to Dovecot. You almost certainly want this. When
`dovecot_ssl_enabled` is false you should not listen on the non-SSL IMAP
port, so set `ports: []`.
``` yaml
    dovecot_imap:
      connection_limit: 16
      clients: 128
      vsz_limit: 256M
      socket: /var/run/dovecot/imap
      ports: [ 143 ]
      ssl_ports: [ 993 ]
```

It is possible to configure namespaces for more advanced uses of Dovecot;
see the Dovecot manual for details.
``` yaml
    dovecot_namespaces: {}
```

## Dependencies

No direct dependencies, but you may need to configure:

 - mysql or mariadb, for dovecot user database and authentication
 - an MTA such as exim or postgres, with rules to deliver local mail to LMTP socket.
 - firewall rules
 - spam or antivirus checks.

You will also need sufficient disk space under `dovecot_dir_storage`; at a
minimum, 256MB/user, but 4GB/user is more likely for active accounts.

## License

MIT / BSD

# Author

This role was based on the work of "practical-ansible", with many changes and
new features by [Ruth Ivimey-Cook](https://www.ivimey.org/) <ruth at ivimey.org>.

