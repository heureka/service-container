# service-container

Dependency injection container with parameters and transaction control.

## Prerequisites

This library is supposed to run with Python 3. No other dependencies are needed.

## Usage

To create service container, just define your dependencies like this:

```python
from servicecontainer import ServiceContainer

sc = ServiceContainer(
    foo=lambda: Foo(),  # service name = service provider
)
```

Service provider must be a callable with none or one argument, which will be the current ServiceContainerTransaction.

Transaction is used to cache service instances. If you don't use transaction, service container will call
service provider each time you retrieve service instance from ServiceContainer.

Note: If you don't create explicit transaction, an implicit throw-away transaction will be created for retrieval
of service instance - that comes into play when resolving sub-dependencies (see lower).

```python
sc.foo  # calls service provider for foo and returns the result (service instance).
sc.foo  # calls service provider again
``` 

To create explicit transaction, use ServiceContainer as a context manager. Use transaction to wrap part of your
code that should reuse the same service instances - eg. handling of one request (if configuration may change between
them). 

Note: Transactions have the same interface as ServiceContainer itself, so in place of ServiceContainer you can
pass ServiceContainerTransaction as well. In multithreaded environment each thread must use it's own transaction though. 

```python
with sc as sct:
    sct.foo  # calls foo_provider and returns the result (service instance).
    sct.foo  # returns the cached service instance.

    sc.foo  # direct access to `sc` circumvents transaction and creates a new instance.
    
with sc as sct:
    sct.foo  # new transaction doesn't have service instance cached, so new instance will be created again.
```

Services may have their own dependencies:

```python
from servicecontainer import ServiceContainer
from your_application import load_configuration
import redis
import pyrq

sc = ServiceContainer(
    config=lambda: load_configuration(),
    redis=lambda sct: redis.Redis(**sct.config['redis']),
    task_queue=lambda sct: pyrq.Queue(sct.config['task_queue_name'], sct.redis)
)

sc.task_queue  # this will create implicit transaction so `config` service is instantiated only once
sc.redis  # will create new implicit transaction though, so `config` and `redis` are instantiated again

with sc as sct:
    sct.task_queue  # creates and returns Queue.
    sct.redis  # was already resolved, so it returns the cached Redis instance.
```

Services can also have parameters. To set those, you must use explicit transactions (parameters are specified for a
transaction).

```python
from servicecontainer import ServiceContainer
from your_application import load_configuration
import redis

sc = ServiceContainer(
    config=lambda: load_configuration(),
    # have different redis for different language versions?
    redis=lambda sct: redis.Redis(**sct.config['redis'][sct.params['lang']]),  
)

with sc(lang="es") as sct:
    sct.redis  # returns redis with configuration for "es" language version
```

Transactions may be nested. For that case, transaction inherits cached instances and set params from parent transaction,
newly set params (params can be only added, not changed) or created instances then influence only that transaction and 
its sub-transactions.

```python
from servicecontainer import ServiceContainer

sc = ServiceContainer(
    config=lambda: load_configuration(),
    redis=lambda sct: redis.Redis(**sct.config['redis'][sct.params['lang']]),  
)

with sc as sct1:
    sct1.config  # creates config instance
    
    with sct1(lang="cz") as sct2:
        sct2.config  # is the cached config from sct1
        sct2.redis  # redis instance cached only in sct2
        
    with sct1(lang="sk") as sct2:
        sct2.redis  # new redis instance, but still using cached config from sct1
```

For more examples and documentation see docstrings.


## Running the tests

```
python3 -m unittest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
