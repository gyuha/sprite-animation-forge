import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/components/AppLayout'
import Dashboard from '@/pages/Dashboard'
import Export from '@/pages/Export'
import Identity from '@/pages/Identity'
import NewCharacter from '@/pages/NewCharacter'
import Plan from '@/pages/Plan'
import Status from '@/pages/Status'
import Studio from '@/pages/Studio'

export const routes = [
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/new', element: <NewCharacter /> },
      { path: '/c/:cid/identity', element: <Identity /> },
      { path: '/c/:cid/plan', element: <Plan /> },
      { path: '/c/:cid/studio/:action?', element: <Studio /> },
      { path: '/c/:cid/export', element: <Export /> },
      { path: '/status', element: <Status /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
