from contextlib import contextmanager
import inspect


class ServiceContainer(object):
    """Used to pass list of services and retrieve fresh instances of service on request.

    Container accepts service definitions in constructor as kwargs mapping service name to a callable,
    that is then used to create the service instance (service provider).

    Callables must accept zero arguments or one argument which will be the current ServiceContainerTransaction.

    >>> sc = ServiceContainer(
    >>>     some_service=lambda: SomeClient(),
    >>>     other_service=lambda sct: OtherClient(sct)),  # sct is ServiceContainerTransaction
    >>> )

    To retrieve a service instance, use provider name as an attribute::

    >>> sc.some_service  # -> instance of SomeClient

    Callables can depend on services in the same container::

    >>> sc = ServiceContainer(
    >>>     config=lambda: load_configuration(),
    >>>     redis=lambda t: load_redis(t.config['redis']),
    >>>     queue=lambda t: Queue("some_queue", t.redis)
    >>> )

    During each retrieval of a service an implicit transaction is created, which caches the service instances created.

    >>> sc = ServiceContainer(
    >>>     obj=lambda: object(),
    >>>     foo_a=lambda t: t.obj,
    >>>     foo_b=lambda t: t.obj,
    >>>     bar=lambda t: t.foo_a is t.foo_b
    >>> )
    >>> sc.bar  # True because one transaction is used.
    True
    >>> sc.foo_a is sc.foo_b  # False because different transactions are used for the two retrievals.
    False

    But if you use the ServiceContainer instead of the transaction, new service will be created for each
    subservice. You probably want to avoid that.

    >>> sc = ServiceContainer(
    >>>     obj=lambda: object(),
    >>>     bar=lambda t: t.obj is t.obj
    >>>     baz=lambda: sc.obj is sc.obj
    >>> )

    >>> sc.bar  # True, because cache is used while retrieving `obj`.
    True
    >>> sc.baz  # False, because cache is circumvented.
    False

    ServiceContainer can be used as a context manager to use transactions explicitly and not recreate services
    for each query, but only when needed::

    >>> sc.obj is sc.obj
    False
    >>> with sc as transaction:
    ...     transaction.obj is transaction.obj
    True

    You can pass params for service providers when creating a transaction (these are accessible as `params` attribute).

    >>> sc = ServiceContainer(
    >>>     connection=lambda t: Connection(db='db_{}'.format(t.params['lang')),
    >>> )
    >>> sc.connection  # Will fail because params['lang'] is not set

    >>> with sc(lang="cz") as sct:
    >>>     sc.connection
    Connection(db='db_cz')

    """
    def __init__(self, **kwargs):
        """Initializes new service container.

        Args:
            **kwargs(callable): Map of service names to service providers (usually lambdas)
        """
        self._service_providers = kwargs

    def _create_transaction(self, params):
        """Returns new empty transaction.

        Args:
            params (dict): Params to set for the new transaction.

        Returns:
            ServiceContainerTransaction: New transaction.
        """
        return ServiceContainerTransaction(self._service_providers.copy(), params=params)

    def __getattr__(self, name):
        """Creates implicit transaction (if needed) and returns service instance from it.

        Args:
            name(str): Name of service provider.

        Returns:
            Service instance as returned by provider.
        """
        return self._create_transaction({}).__getattr__(name)

    def __enter__(self):
        """Enters a transaction.

        Returns:
            ServiceContainerTransaction: New transaction.
        """
        return self._create_transaction({})

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @contextmanager
    def __call__(self, **params):
        """Creates a context manager that will yield new transaction with given `params`.

        Args:
            **params (Any): Params to be set for the transaction

        Yields:
            ServiceContainerTransaction
        """
        yield self._create_transaction(params)


class ServiceContainerTransaction(ServiceContainer):
    def __init__(self, service_providers, services=None, params=None):
        """Initializes a transaction.

        Args:
            service_providers(dict): Own copy of map of service names to service providers.
            services(dict): Cache of service instances to return instead of creating them again in this transaction.
        """
        super().__init__(**service_providers)
        self._service_providers = service_providers
        self._services = {} if services is None else services
        self.params = {} if params is None else params

    def _get_service(self, name):
        """Calls service provider by name and returns whatever it returns.

        Args:
            name(str): Name of service provider to invoke.

        Returns:
            New service instance as returned by provider.
        """
        if name in self._service_providers:
            provider = self._service_providers[name]

            if not callable(provider):
                raise ValueError("Service provider must be callable, got '{}' instead.".format(provider))

            arg_count = len(inspect.signature(provider).parameters)

            if arg_count == 0:
                service = provider()

            elif arg_count == 1:
                service = provider(self)

            else:
                raise ValueError("Service provider must accept 0 or 1 argument (haddr), got {}.".format(arg_count))

            return service

        else:
            raise KeyError('Missing provider for service "{}"'.format(name))

    def _create_transaction(self, params):
        """Returns new transaction with copy of this transaction state.

        Args:
            params (dict): Params to set for the new transaction. Params that are already set cannot be overriden.

        Returns:
            ServiceContainerTransaction: New transaction.
        """
        new_params = self.params.copy()

        for k, v in params.items():
            if k in new_params:
                raise ValueError("Cannot override param '{}', to change it you have to start a fresh transaction."
                                 "".format(k))

            new_params[k] = v

        return ServiceContainerTransaction(self._service_providers.copy(), self._services.copy(), new_params)

    def __getattr__(self, name):
        """Retrieves service instance from transaction cache or creates it if not cached.

        Args:
            name(str): Name of service provider.

        Returns:
            Service instance as returned by provider.
        """
        if name not in self._services:
            self._services[name] = self._get_service(name)

        return self._services[name]
